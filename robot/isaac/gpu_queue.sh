#!/bin/bash
# GPU queue, 2026-09-21 -> 2026-10-01. One job at a time (PhysX needs the GPU to itself).
# Each job: short smoke -> full distillation -> evaluation. A failed smoke skips the full run.
# Disk guard: stop starting new jobs below 8 GB free.
cd ~/extreme-parkour/legged_gym/legged_gym/scripts
PY="$HOME/bin/micromamba run -r $HOME/micromamba -n py38 python"
S=~/snn_parkour_fpga/robot/isaac
Q=~/gpu_queue.log
say() { echo "$(date '+%m-%d %H:%M') $*" | tee -a $Q; }

say "queue armed; waiting for the distillation chain already running"
while ps -eo args | grep -q "[p]ost_distill.sh"; do sleep 600; done
while ps -eo args | grep -q "[t]rain_fpga_stud[e]nt.py --exptid 200-00-fpga"; do sleep 600; done
say "post-distill chain finished; starting queue"

free_gb() { df -BG --output=avail "$HOME" | tail -1 | tr -dc 0-9; }

job() {
  tag=$1; smoke=$2; full=$3; ev=$4
  if [ "$(free_gb)" -lt 8 ]; then say "SKIP $tag: only $(free_gb) GB free"; return; fi
  say "== $tag SMOKE"
  eval "timeout 3600 $smoke" > "$HOME/q_${tag}_smoke.log" 2>&1; rc=$?
  if [ $rc -ne 0 ] || grep -qE "Traceback|CUDA error|out of memory" "$HOME/q_${tag}_smoke.log"; then
    say "$tag SMOKE FAILED (exit $rc); skipping the full run"
    grep -E "Traceback|Error" -A3 "$HOME/q_${tag}_smoke.log" | tail -8 | tee -a $Q
    return
  fi
  say "$tag smoke ok"
  say "== $tag FULL (expect ~39 h)"
  eval "$full" > "$HOME/q_${tag}.log" 2>&1; rc=$?
  say "$tag full exit $rc, last $(grep -oE 'Learning iteration [0-9]+/[0-9]+' "$HOME/q_${tag}.log" | tail -1)"
  if [ -n "$ev" ]; then
    say "== $tag EVAL"
    eval "timeout 3600 $ev" > "$HOME/q_${tag}_eval.log" 2>&1
    say "$tag eval exit $?"
    grep -E '^policy|^\|' "$HOME/q_${tag}_eval.log" | tee -a $Q
  fi
  say "$tag done; $(free_gb) GB free"
}

T="--resume --resumeid 100-00-teacher --use_camera --delay --no_wandb"

# 1. the paper's own depth student: the same-stack reference this project has never had
job stock \
  "$PY train.py --exptid 400-00-stock-smoke $T --seed 1 --max_iterations 150 --headless" \
  "$PY train.py --exptid 400-01-stock $T --seed 1 --max_iterations 10000 --headless" \
  "$PY $S/evaluate_parkour.py --exptid 400-91-eval --resume --resumeid 400-01-stock --use_camera --no_wandb --policy student --steps 1500 --out $HOME/eval_stock.json"

# 2, 3. two more independent FPGA-student runs: a success rate needs a spread, not a point (C0050)
for sd in 2 3; do
  job "fpga_s$sd" \
    "$PY $S/train_fpga_student.py --exptid 410-0${sd}-fpga-smoke $T --seed $sd --iters 150" \
    "$PY $S/train_fpga_student.py --exptid 410-1${sd}-fpga-s$sd $T --seed $sd --iters 10000" \
    "$PY $S/evaluate_parkour.py --exptid 410-9${sd}-eval --resume --resumeid 100-00-teacher --use_camera --no_wandb --policy fpga --fpga_run 410-1${sd}-fpga-s$sd --steps 1500 --out $HOME/eval_fpga_s${sd}.json"
done

# 4. C0047: four consecutive event windows instead of one frame repeated over T
job consec \
  "$PY $S/train_fpga_student.py --exptid 420-00-consec-smoke $T --seed 1 --iters 150 --window consecutive" \
  "$PY $S/train_fpga_student.py --exptid 420-01-consec $T --seed 1 --iters 10000 --window consecutive" \
  "$PY $S/evaluate_parkour.py --exptid 420-91-eval --resume --resumeid 100-00-teacher --use_camera --no_wandb --policy fpga --fpga_run 420-01-consec --window consecutive --steps 1500 --out $HOME/eval_consec.json"

say "QUEUE-DONE"
