#!/usr/bin/env bash
# Overnight AXIS-wrapper stress (2026-09-19): the baked (synthesis) engine
# variants through the hostile-handshake harness under MANY random
# gap/backpressure seeds, both engines, both datasets. The ladder runs one
# seed (7); silicon only ever sees the DMA's handshake pattern. A failure
# here is a wrapper/engine handshake bug that neither has exercised.
# Usage: bash experiments/axis_stress/run_stress.sh <first_seed> <last_seed>
set -u
cd "$(dirname "$0")/../.."
log=experiments/axis_stress/stress_$(date +%Y%m%d_%H%M).log
echo "# seed dataset config result   (started $(date))" > "$log"
for seed in $(seq "$1" "$2"); do
  for ds in c1 g1; do
    for cfg in "ENGINE=1 K=4" "DP=4"; do
      out=$(env BW=1 SEED=$seed $cfg bash sim/run_axis_tb.sh $ds 2>&1 | grep -E "TB_PASS|TB_FAIL|MISMATCH" | tail -1)
      case "$out" in *TB_PASS*) r=PASS;; *) r="FAIL: $out";; esac
      echo "$seed $ds \"$cfg\" $r" >> "$log"
    done
  done
done
echo "# finished $(date): $(grep -c ' PASS$' "$log") pass, $(grep -c FAIL "$log") fail" >> "$log"
