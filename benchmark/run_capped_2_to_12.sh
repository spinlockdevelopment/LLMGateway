#!/usr/bin/env bash
# 12-phase local-only rerun for the capped variant.
#
# - Local-coding (qwen3.6-35b :8082) with thinking on, max_tokens=2048.
# - Seeds Phase 2 from the existing ModelB_capped/phase_01 (Phase 1 11/11 pass).
# - Tees `docker logs llm-gateway` to one rolling file per phase.
# - Commits each phase's workdir to the current git branch after self-eval.
#
# Cross-eval and final-eval are NOT run here — they can be invoked later
# against the committed snapshots.

set -u
cd "$(dirname "$0")"
PY=./.venv/bin/python
CONTAINER=llm-gateway
OUTDIR=results/run_capped
mkdir -p "$OUTDIR"

# NOTE: Despite the script name and `_capped` suffix, MAX_TOKENS is 4096.
# The original capped (2048) run failed on Phase 2 because the model
# truncated mid-tool-call when writing parser.py (~3000 tokens). Switching
# back to 4096 fixes the truncation; we keep the suffix for continuity with
# the already-committed Phase 1 (which is 11/11 pass, our best Phase 1).
LITELLM_ID=local-coding
MAX_TOKENS=4096
SUFFIX=_capped
LABEL=B_capped

START_PHASE=2
END_PHASE=12

# Single docker logs tee for the whole run (one file per phase).
run_phase() {
  local n="$1"
  local phase_num
  phase_num=$(printf "%02d" "$n")

  echo
  echo "================================================================"
  echo "PHASE $phase_num   $(date '+%H:%M:%S')"
  echo "================================================================"

  local logfile="$OUTDIR/phase_${phase_num}.litellm.log"
  : > "$logfile"
  docker logs --since=1s -f "$CONTAINER" >> "$logfile" 2>&1 &
  local logger_pid=$!

  local start=$(date +%s)
  $PY harness.py \
      --litellm-id "$LITELLM_ID" \
      --max-tokens "$MAX_TOKENS" \
      --workdir-suffix "$SUFFIX" \
      --label "$LABEL" \
      phase --num "$n" --model B \
      > "$OUTDIR/phase_${phase_num}.harness.log" 2>&1
  local rc=$?
  local end=$(date +%s)
  local elapsed=$((end - start))

  kill "$logger_pid" 2>/dev/null
  wait "$logger_pid" 2>/dev/null

  echo "rc=$rc   elapsed=${elapsed}s"
  tail -6 "$OUTDIR/phase_${phase_num}.harness.log"

  # Commit the snapshot to the current git branch.
  local wd="ModelB${SUFFIX}/phase_${phase_num}"
  if [ -d "$wd" ]; then
    (cd .. && git add "benchmark/$wd" "benchmark/results/self_eval/${LABEL}/phase_${phase_num}.json" "benchmark/results/timings.csv" "benchmark/results/transcripts/phase_${phase_num}_B_implement.json" "benchmark/results/transcripts/phase_${phase_num}_B_selfeval.json" 2>/dev/null
     git commit -m "benchmark ${LABEL} phase ${phase_num} — local capped" >/dev/null 2>&1)
    echo "committed $wd"
  else
    echo "WARNING: workdir $wd missing — not committing phase $phase_num"
  fi

  if [ $rc -ne 0 ]; then
    echo "harness rc=$rc; stopping at phase $phase_num"
    return 1
  fi
}

for n in $(seq "$START_PHASE" "$END_PHASE"); do
  run_phase "$n" || break
done

echo
echo "================================================================"
echo "RUN COMPLETE   $(date '+%H:%M:%S')"
echo "================================================================"
grep -E ",${LABEL}," results/timings.csv
