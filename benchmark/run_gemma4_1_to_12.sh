#!/usr/bin/env bash
# Run: Gemma-4 26B-A4B (~27B-class MoE, ~4B active), phases 1-12, 64K ctx, with
# the iterating fix loop. This is the post-qwen3.6 attempt — Gemma 4 is not a
# `<think>` model in the same way Qwen3 is, so the parser-500-from-thinking-budget
# trap that broke runs B_qwen36 and B_qwen36_iter should not apply here.
#
# Why this model: Qwen3.6-35B-A3B bracketed an unhittable target — thinking on
# truncated tool calls (peg-native 500), thinking off broke the agent's planning.
# Gemma 4 26B-A4B is the same effective-active-params class (E4B / A4B == ~4B
# active) but a different family, different chat template, different tool-call
# convention. We try it before escalating to headless SSH.
#
# Iteration policy and per-phase commit shape are identical to run_qwen36_iter:
#  - run `phase --num N` once.
#  - then `fix --num N --attempt K` while pytest pass count strictly increases.
#  - cap MAX_FIX. Track per-iteration wall + pass count.

set -u
cd "$(dirname "$0")"

PY=./.venv/bin/python

export LITELLM_URL="${LITELLM_URL:-http://127.0.0.1:8083/v1}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-any}"

# Model alias must match the `-a` flag passed to llama-server (see launch hint
# in SESSION_STATE.md NEXT SESSION block).
LITELLM_ID="${LITELLM_ID:-gemma-4-26b-a4b}"
MAX_TOKENS="${MAX_TOKENS:-8192}"
SUFFIX=_gemma4
LABEL=B_gemma4
# Plain tool_choice=required — no enable_thinking flag (Gemma 4's thinking
# behavior is template-controlled; the pitfall #2 escape hatch is qwen-specific).
EXTRA_BODY='{"tool_choice":"required"}'

START_PHASE="${START_PHASE:-1}"
END_PHASE="${END_PHASE:-12}"
MAX_FIX="${MAX_FIX:-4}"

OUTDIR=results/run_gemma4
mkdir -p "$OUTDIR"
ITER_LOG="$OUTDIR/iterations.tsv"
if [ ! -s "$ITER_LOG" ]; then
  printf "phase\tstage\tattempt\telapsed_s\tpassed\tfailed\tfinish\n" > "$ITER_LOG"
fi

pass_count_for_phase() {
  local phase="$1"
  awk -F',' -v ph="$phase" -v lab="$LABEL" '
    $1==ph && $2==lab && $9!="" { passed=$9 }
    END { print passed+0 }
  ' results/timings.csv
}

last_row_for() {
  local phase="$1" stage_match="$2"
  awk -F',' -v ph="$phase" -v lab="$LABEL" -v sm="$stage_match" '
    $1==ph && $2==lab && index($3, sm)==1 {
      elapsed=$4; finish=$8; passed=$9; failed=$10; stage=$3
    }
    END { printf "%s\t%s\t%s\t%s\n", stage, elapsed, passed, failed }
  ' results/timings.csv
}

commit_phase() {
  local phase="$1"
  local phase_num
  phase_num=$(printf "%02d" "$phase")
  local wd="ModelB${SUFFIX}/phase_${phase_num}"
  if [ ! -d "$wd" ]; then
    echo "WARNING: workdir $wd missing — not committing phase $phase_num"
    return
  fi
  (cd .. && git add \
      "benchmark/$wd" \
      "benchmark/results/self_eval/${LABEL}/phase_${phase_num}.json" \
      "benchmark/results/timings.csv" \
      "benchmark/results/transcripts/phase_${phase_num}_B_implement.json" \
      "benchmark/results/transcripts/phase_${phase_num}_B_selfeval.json" \
      "benchmark/results/transcripts/phase_${phase_num}_B_fix_"*.json \
      "benchmark/results/baselines/${LABEL}/phase_${phase_num}_junit.xml" \
      "benchmark/results/baselines/${LABEL}/phase_${phase_num}_passed.json" \
      "benchmark/$OUTDIR/phase_${phase_num}.harness.log" \
      "benchmark/$OUTDIR/phase_${phase_num}.fix_"*.log \
      "benchmark/$ITER_LOG" 2>/dev/null
   git commit -m "benchmark ${LABEL} phase ${phase_num} — gemma-4-26b-a4b @ 64K, iterated" >/dev/null 2>&1)
  echo "committed $wd"
}

run_phase() {
  local n="$1"
  local phase_num
  phase_num=$(printf "%02d" "$n")

  echo
  echo "================================================================"
  echo "PHASE $phase_num   $(date '+%H:%M:%S')"
  echo "================================================================"

  local start end
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
  end=$(date +%s)
  echo "[phase] rc=$rc   elapsed=$((end-start))s"
  tail -8 "$OUTDIR/phase_${phase_num}.harness.log"

  local row passed
  row=$(last_row_for "$n" "self_eval")
  passed=$(pass_count_for_phase "$n")
  printf "%s\tphase\t0\t%s\t%s\tinitial\n" "$phase_num" \
    "$(echo "$row" | cut -f2)" "$(echo "$row" | cut -f3,4)" >> "$ITER_LOG"

  if [ $rc -ne 0 ]; then
    echo "[phase] harness rc=$rc; committing and stopping at phase $phase_num"
    commit_phase "$n"
    return 1
  fi

  local prev="$passed"
  local k
  for k in $(seq 1 "$MAX_FIX"); do
    echo
    echo "---- phase ${phase_num} fix attempt $k (prev passed=${prev}) ----"
    start=$(date +%s)
    $PY harness.py \
        --litellm-id "$LITELLM_ID" \
        --max-tokens "$MAX_TOKENS" \
        --workdir-suffix "$SUFFIX" \
        --label "$LABEL" \
        --extra-body-json "$EXTRA_BODY" \
        fix --num "$n" --model B --attempt "$k" \
        > "$OUTDIR/phase_${phase_num}.fix_$(printf '%02d' "$k").log" 2>&1
    rc=$?
    end=$(date +%s)
    echo "[fix#$k] rc=$rc   elapsed=$((end-start))s"
    tail -6 "$OUTDIR/phase_${phase_num}.fix_$(printf '%02d' "$k").log"

    local stage="fix_$(printf '%02d' "$k")"
    row=$(last_row_for "$n" "$stage")
    local now
    now=$(pass_count_for_phase "$n")
    printf "%s\tfix\t%s\t%s\t%s\t%s\t%s\n" "$phase_num" "$k" \
      "$(echo "$row" | cut -f2)" "$(echo "$row" | cut -f3)" \
      "$(echo "$row" | cut -f4)" "$(echo "$row" | cut -f1)" >> "$ITER_LOG"

    if [ $rc -ne 0 ]; then
      echo "[fix#$k] harness rc=$rc; stopping iterations for phase $phase_num"
      break
    fi
    if [ "$now" -le "$prev" ]; then
      echo "[fix#$k] no progress (passed ${now} <= prev ${prev}); stopping iterations"
      break
    fi
    echo "[fix#$k] progress: passed ${prev} -> ${now}; continuing"
    prev="$now"
  done

  commit_phase "$n"
}

echo "Starting phases ${START_PHASE}..${END_PHASE} (MAX_FIX=${MAX_FIX}) at $(date)"
RUN_START=$(date +%s)
for n in $(seq "$START_PHASE" "$END_PHASE"); do
  run_phase "$n" || { echo "ABORT at phase $n"; break; }
done
RUN_END=$(date +%s)

echo
echo "================================================================"
echo "RUN COMPLETE   $(date '+%H:%M:%S')   total=$((RUN_END-RUN_START))s"
echo "================================================================"
echo "--- iterations.tsv ---"
column -t -s $'\t' "$ITER_LOG"
echo
echo "--- timings.csv rows for ${LABEL} ---"
grep -E ",${LABEL}," results/timings.csv | tail -60
