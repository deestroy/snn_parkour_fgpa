#!/bin/bash
# DVS-Gesture seed 0 at T=8 and T=16 (checkpoints were not retained): train -> quantise -> golden, then the C0046 costing at fc k=7 / k=6.
cd ~/snn_parkour_fpga; PY=~/esparkour_venv/bin/python; C=experiments/dvsgesture/c0046
for T in 8 16; do
  D=experiments/dvsgesture/t$T; ck=$D/dvsgesture_beta0875_seed0_t$T.pt
  $PY train/03_train.py --dataset dvsgesture --T $T --epochs 30 --seed 0 --device cuda --save $ck > $D/train_seed0.log 2>&1; echo "TRAIN T=$T exit $? $(date +%H:%M)"
  mv experiments/m0_firing_rates_binarised_dvsgesture_seed0_t$T.csv $D/seed0_m0_firing_rates_binarised.csv 2>/dev/null
  $PY train/05_quantise.py --ckpt $ck --device cuda --out $D/dvsgesture_weights_int8_seed0_t$T.npz > $D/quantise_seed0.log 2>&1; echo "QUANT T=$T exit $?"
  $PY train/06_golden_check.py --ckpt $ck --weights $D/dvsgesture_weights_int8_seed0_t$T.npz --traces /tmp/tr_s0_t$T.npz > $D/golden_check_seed0.log 2>&1; echo "GOLDEN T=$T exit $?"; rm -f /tmp/tr_s0_t$T.npz
  ks=$(grep -E "^(conv1|conv2|conv3) " $D/quantise_seed0.log | awk "{print \$3}" | tr "\n" "," )
  for fck in 7 6; do
    tag=t${T}_seed0
    $PY train/05_quantise.py --ckpt $ck --fixed_k ${ks}$fck --device cpu --out $C/${tag}_fck${fck}_int8.npz > $C/quantise_${tag}_fck$fck.log 2>&1
    $PY train/06_golden_check.py --ckpt $ck --weights $C/${tag}_fck${fck}_int8.npz --traces /tmp/tr_c0046.npz > $C/golden_${tag}_fck$fck.log 2>&1; rm -f /tmp/tr_c0046.npz
    grep -E "golden integer|fc  V in" $C/golden_${tag}_fck$fck.log
  done
done
echo SEED0-RERUN-DONE $(date +%H:%M)
