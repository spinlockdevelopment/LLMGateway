#!/usr/bin/env bash
# Iterating run: Qwen3.6-35B-A3B (hybrid attention+SSM), phases 1-12, 64K ctx,
# thinking DISABLED, with per-phase fix-iteration loop.
#
# Lessons from run B_qwen36 (see results/run_qwen36.md):
#  - `peg-native` parser 500s when max_tokens=4096 truncates trailing tool-call
#    XML; the thinking model wastes the budget on <think>. Fix: disable thinking
#    via chat_template_kwargs.enable_thinking=false, AND bump max_tokens to 8192.
#  - Phase 2 selfeval wrote partial parser.py before its own 500, poisoning
#    every later phase's seed. Fix: fresh ModelB_qwen36_iter/ root + per-phase
#    fix iteration so the model gets multiple chances to repair a broken seed
#    while it is still making progress.
#
# Iteration policy:
#  - Run `phase --num N` once (implement + selfeval + pytest).
#  - Read pass count P0.
#  - For attempt K = 1..MAX_FIX:
#      run `fix --num N --attempt K`
#      read pass count P_K
#      if P_K <= P_prev: STOP iterating (no progress).
#      else: P_prev = P_K, continue.
#  - Commit phase + all fix transcripts together.
#  - Per-iteration wall time is recorded in results/timings.csv as stage `fix_KK`
#    and aggregated into $ITER_LOG below.

set -u
cd "$(dirname "$0")"

PY=./.venv/bin/python

export LITELLM_URL="${LITELLM_URL:-http://127.0.0.1:8083/v1}"
export LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-any}"

LITELLM_ID=qwen3.6-35b-a3b
MAX_TOKENS=8192
SUFFIX=_qwen36_iter
LABEL=B_qwen36_iter
# enable_thinking=false is the key change vs run_qwen36_1_to_12.sh
EXTRA_BODY='{"tool_choice":"required","chat_template_kwargs":{"enable_thinking":false}}'

START_PHASE="${START_PHASE:-1}"
END_PHASE="${END_PHASE:-12}"
MAX_FIX="${MAX_FIX:-4}"     # hard cap on fix attempts per phase

OUTDIR=results/run_qwen36_iter
mkdir -p "$OUTDIR"
ITER_LOG="$OUTDIR/iterations.tsv"
if [ ! -s "$ITER_LOG" ]; then
  printf "phase\tstage\tattempt\telapsed_s\tpassed\tfailed\tfinish\n" > "$ITER_LOG"
fi

# Read pass count from the most recently appended row in timings.csv for this
# phase + label. Robust to whatever stage name (phase/self_eval/fix_KK).
pass_count_for_phase() {
  local phase="$1"
  # timings.csv columns: phase,model,stage,elapsed_s,steps,in_tok,out_tok,finish,passed,failed
  # We want the LAST row for this phase + LABEL where passed is non-empty.
  awk -F',' -v ph="$phase" -v lab="$LABEL" '
    $1==ph && $2==lab && $9!="" { passed=$9 }
    END { print passed+0 }
  ' results/timings.csv
}

# Last-row elapsed/finish for the most recent (phase, stage_prefix) — used to mirror
# into iterations.tsv for at-a-glance reading. stage_prefix is exact ("self_eval") or
# a prefix ("fix_") match for fix attempts.
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
   git commit -m "benchmark ${LABEL} phase ${phase_num} — qwen3.6-35b-a3b @ 64K, thinking off, iterated" >/dev/null 2>&1)
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

  # 1) Initial implement + selfeval + pytest.
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
  printf "%s\tphase\t0\t%s\t%s\n" "$phase_num" "$(echo "$row" | cut -f2)" "$(echo "$row" | cut -f3,4)" \
    | awk -F'\t' '{printf "%s\t%s\t%s\t%s\t%s\t%s\tinitial\n",$1,$2,$3,$4,$5,$6}' >> "$ITER_LOG"

  if [ $rc -ne 0 ]; then
    echo "[phase] harness rc=$rc; committing and stopping at phase $phase_num"
    commit_phase "$n"
    return 1
  fi

  # 2) Iterate fix attempts while passing count strictly increases.
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
    printf "%s\tfix\t%s\t%s\t%s\t%s\n" "$phase_num" "$k" \
      "$(echo "$row" | cut -f2)" "$(echo "$row" | cut -f3)" "$(echo "$row" | cut -f4)" \
      | awk -F'\t' -v fin="$(echo "$row" | cut -f1)" '{printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n",$1,$2,$3,$4,$5,$6,fin}' >> "$ITER_LOG"

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
