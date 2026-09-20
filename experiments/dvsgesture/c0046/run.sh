#!/bin/bash
# C0046 option costing: requantise the overflowing DVS-Gesture networks with the FC shift one/two
# steps coarser (k=7, k=6; conv shifts as chosen), then golden-check accuracy and fc membrane use.
cd ~/snn_parkour_fpga
PY=~/esparkour_venv/bin/python3
OUT=experiments/dvsgesture/c0046
run() {  # run <tag> <ckpt> <c1> <c2> <c3> <fck>
  tag=$1; ck=$2; ks="$3,$4,$5,$6"
  echo "== $tag fixed_k=$ks $(date +%H:%M:%S)"
  $PY train/05_quantise.py --ckpt $ck --fixed_k $ks --device cpu --out $OUT/${tag}_fck$6_int8.npz > $OUT/quantise_${tag}_fck$6.log 2>&1
  $PY train/06_golden_check.py --ckpt $ck --weights $OUT/${tag}_fck$6_int8.npz --traces /tmp/tr_c0046.npz > $OUT/golden_${tag}_fck$6.log 2>&1
  rm -f /tmp/tr_c0046.npz
  grep -E "^fc |golden integer|fc  V in" $OUT/quantise_${tag}_fck$6.log $OUT/golden_${tag}_fck$6.log
}
for fck in 7 6; do
  run t16_seed1 experiments/dvsgesture/t16/dvsgesture_beta0875_seed1_t16.pt 7 8 8 $fck
  run t16_seed2 experiments/dvsgesture/t16/dvsgesture_beta0875_seed2_t16.pt 6 7 8 $fck
  run t8_seed1  experiments/dvsgesture/t8/dvsgesture_beta0875_seed1_t8.pt   7 8 8 $fck
  run t8_seed2  experiments/dvsgesture/t8/dvsgesture_beta0875_seed2_t8.pt   6 7 8 $fck
  run t4_rate0.30_seed0 experiments/rate_sweep_dvsg/dvsg_rate0.30_seed0.pt 6 8 8 $fck
  run t4_rate0.30_seed1 experiments/rate_sweep_dvsg/dvsg_rate0.30_seed1.pt 6 8 8 $fck
  run t4_rate0.30_seed2 experiments/rate_sweep_dvsg/dvsg_rate0.30_seed2.pt 6 7 8 $fck
done
echo "C0046-DONE $(date +%H:%M:%S)"
