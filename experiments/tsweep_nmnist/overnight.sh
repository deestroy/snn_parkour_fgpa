#!/bin/bash
# Overnight on the MI210 (2026-09-19 23:55): (A) N-MNIST T=8/16 x 3 seeds; (B) DVS-Gesture T=8 rate sweep; (C) DVS-Gesture T=16 seeds 1-2. Sequential.
cd ~/snn_parkour_fpga; PY=~/esparkour_venv/bin/python; PK=~/nmnist_prep_venv/bin/python; N=experiments/tsweep_nmnist
for T in 8 16; do
  $PK train/04_pack_dataset.py --T $T > $N/pack_t$T.log 2>&1; echo "PACK N-MNIST T=$T exit $? $(date +%H:%M)"
  for s in 0 1 2; do
    ck=$N/nmnist_t${T}_seed$s.pt
    $PY train/03_train.py --T $T --epochs 10 --seed $s --device cuda --save $ck > $N/train_t${T}_seed$s.log 2>&1; echo "TRAIN T=$T s$s exit $?"
    mv experiments/m0_firing_rates_binarised_nmnist_seed${s}_t$T.csv $N/ 2>/dev/null
    $PY train/05_quantise.py --ckpt $ck --device cuda --out $N/nmnist_t${T}_seed${s}_int8.npz > $N/quantise_t${T}_seed$s.log 2>&1
    $PY train/06_golden_check.py --ckpt $ck --weights $N/nmnist_t${T}_seed${s}_int8.npz --traces /tmp/tr_nt_${T}_$s.npz > $N/golden_t${T}_seed$s.log 2>&1; echo "GOLDEN T=$T s$s exit $?"; rm -f /tmp/tr_nt_${T}_$s.npz
  done
done
D=experiments/rate_sweep_dvsg/t8
for r in 0.02 0.04 0.08 0.16 0.30; do
  ck=$D/dvsg_t8_rate${r}_seed0.pt
  $PY train/03_train.py --dataset dvsgesture --T 8 --epochs 30 --device cuda --rate_target $r --rate_lambda 100 --seed 0 --save $ck > $D/train_rate$r.log 2>&1; echo "DVSG T=8 TRAIN $r exit $?"
  mv experiments/rates_binarised_dvsgesture_target*${r}*_seed0_t8.csv $D/ 2>/dev/null
  $PY train/05_quantise.py --ckpt $ck --device cuda --out $D/dvsg_t8_rate${r}_int8.npz > $D/quantise_rate$r.log 2>&1
  $PY train/06_golden_check.py --ckpt $ck --weights $D/dvsg_t8_rate${r}_int8.npz --traces /tmp/tr_d8_$r.npz > $D/golden_rate$r.log 2>&1; echo "DVSG T=8 GOLDEN $r exit $?"; rm -f /tmp/tr_d8_$r.npz
done
D=experiments/dvsgesture/t16
for s in 1 2; do
  ck=$D/dvsgesture_beta0875_seed${s}_t16.pt
  $PY train/03_train.py --dataset dvsgesture --T 16 --epochs 30 --seed $s --device cuda --save $ck > $D/train_seed$s.log 2>&1; echo "DVSG T=16 TRAIN s$s exit $?"
  mv experiments/m0_firing_rates_binarised_dvsgesture_seed${s}_t16.csv $D/seed${s}_m0_firing_rates_binarised.csv 2>/dev/null
  $PY train/05_quantise.py --ckpt $ck --device cuda --out $D/dvsgesture_weights_int8_seed${s}_t16.npz > $D/quantise_seed$s.log 2>&1
  $PY train/06_golden_check.py --ckpt $ck --weights $D/dvsgesture_weights_int8_seed${s}_t16.npz --traces /tmp/tr_d16_$s.npz > $D/golden_check_seed$s.log 2>&1; echo "DVSG T=16 GOLDEN s$s exit $?"; rm -f /tmp/tr_d16_$s.npz
done
echo "OVERNIGHT-DONE $(date)"
