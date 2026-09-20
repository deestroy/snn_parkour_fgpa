#!/bin/bash
# DVS-Gesture T=8, seeds 1 and 2 on the MI210: train -> quantise -> golden
cd ~/snn_parkour_fpga; PY=~/esparkour_venv/bin/python; D=experiments/dvsgesture/t8
for s in 1 2; do
  ck=$D/dvsgesture_beta0875_seed${s}_t8.pt
  $PY train/03_train.py --dataset dvsgesture --T 8 --epochs 30 --seed $s --device cuda --save $ck > $D/train_seed$s.log 2>&1; echo "TRAIN seed $s exit $?"
  mv experiments/m0_firing_rates_binarised_dvsgesture_seed${s}_t8.csv $D/seed${s}_m0_firing_rates_binarised.csv 2>/dev/null
  $PY train/05_quantise.py --ckpt $ck --device cuda --out $D/dvsgesture_weights_int8_seed${s}_t8.npz > $D/quantise_seed$s.log 2>&1; echo "QUANT seed $s exit $?"
  $PY train/06_golden_check.py --ckpt $ck --weights $D/dvsgesture_weights_int8_seed${s}_t8.npz --traces /tmp/traces_t8_s$s.npz > $D/golden_check_seed$s.log 2>&1; echo "GOLDEN seed $s exit $?"; rm -f /tmp/traces_t8_s$s.npz
done; echo T8-SEEDS-DONE
