#!/usr/bin/env bash
# 12-phase local-only run for Qwen2.5-Coder-14B-Instruct (Q4_K_M) at native 32K.
#
# - Talks to llama-server directly on :8083, bypassing LiteLLM.
# - tool_choice="required" via --extra-body-json — Qwen2.5-Coder emits raw
#   <tools> text under tool_choice=auto, breaking the harness's tool_calls
#   parsing. Required forces the grammar path which produces well-formed
#   structured tool calls.
# - Per-phase commit of workdir + self-eval JSON + timings.csv.
# - Phase 2..N seed from phase 1's working dir automatically via the harness.

set -u
cd "$(dirname "$0")"

PY=./.venv/bin/python

export LITELLM_URL="${LITELLM_URL:-http://127.0.0.1:8083/v1}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-any}"

LITELLM_ID=qwen2.5-coder-14b
MAX_TOKENS=4096
SUFFIX=_14bcoder
LABEL=B_14bcoder
EXTRA_BODY='{"tool_choice":"required"}'

# Phase 1 was already committed by the standalone trial. Resume at 2 by default.
START_PHASE="${START_PHASE:-2}"
END_PHASE="${END_PHASE:-12}"

OUTDIR=results/run_14bcoder
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
     git commit -m "benchmark ${LABEL} phase ${phase_num} — qwen2.5-coder-14b Q4_K_M @ 32K" >/dev/null 2>&1)
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
