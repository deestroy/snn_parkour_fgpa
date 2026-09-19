#!/bin/bash
# DVS-Gesture activity axis: seed 0, T=4, 30 epochs, lambda 100, five targets; calibration first (3 epochs at 0.04)
cd ~/snn_parkour_fpga; PY=~/esparkour_venv/bin/python; D=experiments/rate_sweep_dvsg
$PY train/03_train.py --dataset dvsgesture --epochs 3 --device cuda --rate_target 0.04 --rate_lambda 100 --seed 0 > $D/calib_lambda100.log 2>&1; echo "CALIB: $(grep -E "^epoch  3" $D/calib_lambda100.log)"
rm -f experiments/rates_binarised_dvsgesture_target0.040_seed0_t4.csv
for r in 0.02 0.04 0.08 0.16 0.30; do
  ck=$D/dvsg_rate${r}_seed0.pt
  $PY train/03_train.py --dataset dvsgesture --epochs 30 --device cuda --rate_target $r --rate_lambda 100 --seed 0 --save $ck > $D/train_rate$r.log 2>&1; echo "TRAIN $r exit $?"
  mv experiments/rates_binarised_dvsgesture_target${r}0_seed0_t4.csv $D/ 2>/dev/null || mv experiments/rates_binarised_dvsgesture_target*${r}*_seed0_t4.csv $D/ 2>/dev/null
  $PY train/05_quantise.py --ckpt $ck --device cuda --out $D/dvsg_rate${r}_int8.npz > $D/quantise_rate$r.log 2>&1; echo "QUANT $r exit $?"
  $PY train/06_golden_check.py --ckpt $ck --weights $D/dvsg_rate${r}_int8.npz --traces $D/traces_rate$r.npz > $D/golden_rate$r.log 2>&1; echo "GOLDEN $r exit $?"
done; echo SWEEP-DONE
