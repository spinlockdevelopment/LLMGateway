#!/usr/bin/env bash
# Run Phase 1 three ways on the local model to compare reasoning configs.
# Tees `docker logs llm-gateway` into a per-variant file for triage.
#
# Variants:
#   thinkon   = local-coding (default), max_tokens=4096   — the config from the first run
#   thinkoff  = local-coding + chat_template_kwargs.enable_thinking=false, max_tokens=4096
#   capped    = local-coding, max_tokens=2048             — thinking on, output capped
#
# Note: the LiteLLM "local-reason" route is misconfigured (points at port 8084
# with no server). We pass enable_thinking=false inline via --extra-body-json
# against the working local-coding route (port 8082).
#
# Each variant lands in benchmark/ModelB_<variant>/phase_01/. Tee logs go to
# benchmark/results/exp_phase1/<variant>.litellm.log.

set -u
cd "$(dirname "$0")"

OUTDIR=results/exp_phase1
mkdir -p "$OUTDIR"

PY=./.venv/bin/python
CONTAINER=llm-gateway

run_variant() {
  local name="$1"
  local litellm_id="$2"
  local max_tokens="$3"
  local extra_body="$4"   # may be empty

  echo
  echo "================================================================"
  echo "VARIANT: $name   litellm-id=$litellm_id   max_tokens=$max_tokens"
  echo "extra_body: $extra_body"
  echo "================================================================"

  # Wipe any prior run of this variant
  rm -rf "ModelB_${name}/phase_01"

  # Start docker logs tee (since=1s avoids pulling backlog)
  local logfile="$OUTDIR/${name}.litellm.log"
  : > "$logfile"
  docker logs --since=1s -f "$CONTAINER" >> "$logfile" 2>&1 &
  local logger_pid=$!

  # Build harness args
  local args=(
      --litellm-id "$litellm_id"
      --max-tokens "$max_tokens"
      --workdir-suffix "_${name}"
      --label "B_${name}"
  )
  if [ -n "$extra_body" ]; then
      args+=(--extra-body-json "$extra_body")
  fi
  args+=(phase --num 1 --model B)

  # Run the variant
  local start=$(date +%s)
  $PY harness.py "${args[@]}" > "$OUTDIR/${name}.harness.log" 2>&1
  local rc=$?
  local end=$(date +%s)
  local elapsed=$((end - start))

  # Stop tee
  kill $logger_pid 2>/dev/null
  wait $logger_pid 2>/dev/null

  echo "rc=$rc   elapsed=${elapsed}s"
  tail -8 "$OUTDIR/${name}.harness.log"

  # Run pytest to confirm results
  if [ -d "ModelB_${name}/phase_01" ]; then
    echo "--- pytest in ModelB_${name}/phase_01 ---"
    (cd "ModelB_${name}/phase_01" && ../../.venv/bin/python -m pytest -q --tb=no 2>&1 | tail -5)
  fi
}

# Sequence: run each, then summarize
run_variant thinkon  local-coding 4096 ""
run_variant thinkoff local-coding 4096 '{"chat_template_kwargs":{"enable_thinking":false}}'
run_variant capped   local-coding 2048 ""

echo
echo "================================================================"
echo "EXPERIMENT COMPLETE"
echo "================================================================"
echo
echo "Per-variant timings + tests:"
grep -E ",B_(thinkon|thinkoff|capped)," results/timings.csv || echo "(no rows yet)"

echo
echo "LiteLLM log sizes:"
ls -lh "$OUTDIR"/*.litellm.log 2>/dev/null

echo
echo "See:"
echo "  $OUTDIR/<variant>.harness.log     — harness stdout"
echo "  $OUTDIR/<variant>.litellm.log     — docker logs llm-gateway during the run"
echo "  ModelB_<variant>/phase_01/        — the model's workdir"
