#!/usr/bin/env bash
# Full run: Qwen3.6-35B-A3B (hybrid attention+SSM), phases 1-12, at 64K ctx.
# llama-server must be launched with -c 65536 -ctk q8_0 -ctv q8_0 for this run
# (see SESSION_STATE.md "NEXT SESSION" block). Hybrid SSM means long context is
# nearly free; 64K is chosen for low memory pressure, not speed.
#
# - Talks to llama-server directly on :8083, bypassing LiteLLM.
# - tool_choice="required" via --extra-body-json — forces the grammar path so we
#   get well-formed structured tool_calls instead of raw <tools> text.
# - max_tokens >= 4096 (smaller truncates qwen tool calls — see pitfalls memo).
# - Per-phase commit of workdir + self-eval JSON + timings.csv so a long run can
#   be resumed and inspected mid-flight.
# - Phase 2..N seed from phase 1's working dir automatically via the harness.
# - Watch the harness logs for parser-500s ("Failed to parse input"): this is a
#   thinking model with a custom tool-call template under --jinja.

set -u
cd "$(dirname "$0")"

PY=./.venv/bin/python

export LITELLM_URL="${LITELLM_URL:-http://127.0.0.1:8083/v1}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-any}"

LITELLM_ID=qwen3.6-35b-a3b
MAX_TOKENS=4096
SUFFIX=_qwen36
LABEL=B_qwen36
EXTRA_BODY='{"tool_choice":"required"}'

START_PHASE="${START_PHASE:-1}"
END_PHASE="${END_PHASE:-12}"

OUTDIR=results/run_qwen36
mkdir -p "$OUTDIR"

run_phase() {
  local n="$1"
  local phase_num
  phase_num=$(printf "%02d" "$n")

  echo
  echo "================================================================"
  echo "PHASE $phase_num   $(date '+%H:%M:%S')"
  echo "================================================================"

  local start
  start=$(date +%s)
  $PY harness.py \
      --litellm-id "$LITELLM_ID" \
      --max-tokens "$MAX_TOKENS" \
      --workdir-suffix "$SUFFIX" \
      --label "$LABEL" \
      --extra-body-json "$EXTRA_BODY" \
      phase --num "$n" --model B \
      > "$OUTDIR/phase_${phase_num}.harness.log" 2>&1
  local rc=$?
  local end
  end=$(date +%s)
  local elapsed=$((end - start))

  echo "rc=$rc   elapsed=${elapsed}s"
  tail -8 "$OUTDIR/phase_${phase_num}.harness.log"

  local wd="ModelB${SUFFIX}/phase_${phase_num}"
  if [ -d "$wd" ]; then
    (cd .. && git add \
        "benchmark/$wd" \
        "benchmark/results/self_eval/${LABEL}/phase_${phase_num}.json" \
        "benchmark/results/timings.csv" \
        "benchmark/results/transcripts/phase_${phase_num}_B_implement.json" \
        "benchmark/results/transcripts/phase_${phase_num}_B_selfeval.json" \
        "benchmark/results/baselines/${LABEL}/phase_${phase_num}_junit.xml" \
        "benchmark/results/baselines/${LABEL}/phase_${phase_num}_passed.json" \
        "benchmark/$OUTDIR/phase_${phase_num}.harness.log" 2>/dev/null
     git commit -m "benchmark ${LABEL} phase ${phase_num} — qwen3.6-35b-a3b @ 64K" >/dev/null 2>&1)
    echo "committed $wd"
  else
    echo "WARNING: workdir $wd missing — not committing phase $phase_num"
  fi

  if [ $rc -ne 0 ]; then
    echo "harness rc=$rc; stopping at phase $phase_num"
    return 1
  fi
}

echo "Starting phases ${START_PHASE}..${END_PHASE} at $(date)"
RUN_START=$(date +%s)
for n in $(seq "$START_PHASE" "$END_PHASE"); do
  run_phase "$n" || { echo "ABORT at phase $n"; break; }
done
RUN_END=$(date +%s)

echo
echo "================================================================"
echo "RUN COMPLETE   $(date '+%H:%M:%S')   total=$((RUN_END-RUN_START))s"
echo "================================================================"
grep -E ",${LABEL}," results/timings.csv | tail -30
