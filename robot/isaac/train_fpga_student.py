"""Distil the extreme-parkour teacher into the FPGA-sized spiking encoder
inside extreme-parkour's own vision-distillation loop (IsaacGym).

Additive: nothing in extreme-parkour is modified. Mirrors their train.py
(camera envs, --resume from the teacher, --delay), then swaps the depth
encoder's base_backbone for FPGAEventBackbone (events -> 58k spiking conv
encoder), recreates the optimisers that captured the old parameters, and
runs their learn_vision() unchanged.

Run on the NVIDIA box, from extreme-parkour's scripts directory so their
imports resolve exactly as train.py's do:

  cd ~/extreme-parkour/legged_gym/legged_gym/scripts
  ~/bin/micromamba run -r ~/micromamba -n py38 python \\
      ~/snn_parkour_fpga/robot/isaac/train_fpga_student.py \\
      --exptid 200-00-fpga --resume --resumeid 100-00-teacher \\
      --use_camera --delay --no_wandb --iters 10000 [--window repeat|consecutive]

Smoke: add --num_envs 8 --iters 2.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isaacgym                                              # noqa: E402,F401  (must precede torch)
import torch                                                 # noqa: E402
from legged_gym import LEGGED_GYM_ROOT_DIR                   # noqa: E402
from legged_gym.envs import *                                # noqa: E402,F401,F403
from legged_gym.utils import get_args, task_registry         # noqa: E402

from fpga_event_backbone import FPGAEventBackbone            # noqa: E402


def _port_args():
    """Our flags, parsed out before extreme-parkour's get_args sees argv."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--iters", type=int, default=10000)
    p.add_argument("--window", choices=("repeat", "consecutive"), default="repeat")
    p.add_argument("--counts", action="store_true", help="feed event counts/8 instead of binarised frames")
    p.add_argument("--side", type=int, default=64, help="depth resize (square) = encoder input side")
    ours, rest = p.parse_known_args()
    sys.argv = [sys.argv[0]] + rest
    return ours


def main():
    ours = _port_args()
    args = get_args()
    args.headless = True
    assert args.use_camera and args.resume, "needs --use_camera --resume --resumeid <teacher>"
    log_pth = os.path.join(LEGGED_GYM_ROOT_DIR, "logs", args.proj_name, args.exptid)
    os.makedirs(log_pth, exist_ok=True)

    env_cfg, train_cfg = task_registry.get_cfgs(name=args.task)
    env_cfg.depth.resized = (ours.side, ours.side)           # (W, H): square, the encoder's geometry
    env, env_cfg = task_registry.make_env(name=args.task, args=args, env_cfg=env_cfg)
    runner, train_cfg = task_registry.make_alg_runner(log_root=log_pth, env=env, name=args.task,
                                                      args=args, train_cfg=train_cfg)
    alg = runner.alg
    assert alg.depth_encoder is not None, "runner built without a depth encoder (--use_camera?)"

    # --- the swap -----------------------------------------------------------
    bb = FPGAEventBackbone(env, latent_dim=32, T=4, window=ours.window,
                           binarise=not ours.counts).to(runner.device)
    alg.depth_encoder.base_backbone = bb
    lr = alg.depth_encoder_paras["learning_rate"]
    alg.depth_encoder_optimizer = torch.optim.Adam(alg.depth_encoder.parameters(), lr=lr)
    alg.depth_actor_optimizer = torch.optim.Adam(
        [*alg.depth_actor.parameters(), *alg.depth_encoder.parameters()], lr=lr)
    n_enc = sum(p.numel() for p in bb.enc.parameters())
    print("FPGA event backbone in place: %d encoder parameters, window=%s, binarise=%s, "
          "depth %dx%d, far %.1f m, tick every %d steps" % (
              n_enc, ours.window, not ours.counts, ours.side, ours.side, bb.far, bb.tick), flush=True)
    with open(os.path.join(log_pth, "fpga_port.txt"), "w") as fh:
        fh.write("window=%s binarise=%s side=%d encoder_params=%d iters=%d teacher=%s\n"
                 % (ours.window, not ours.counts, ours.side, n_enc, ours.iters, args.resumeid))

    runner.learn_vision(num_learning_iterations=ours.iters, init_at_random_ep_len=True)
    print("event-bit rate at the last tick: %.4f (%d encoder calls)" % (bb.last_rate, bb.n_calls))


if __name__ == "__main__":
    main()
