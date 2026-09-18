"""Record event frames from extreme-parkour (IsaacGym) rollouts for the
FPGA golden-vector export, with the SAME event simulator, depth mapping,
binarisation and tick timing the student trains with (fpga_event_backbone).

Window is `repeat` (the student's direct coding): each saved sample is ONE
camera-tick event frame; sim/export_fpga_student_vectors.py repeats it over
the T = 4 spiking timesteps. The file records `window` so the exporter can
refuse a mismatch.

The environments are driven by the TEACHER (scandots) policy loaded via
--resume/--resumeid, so frames can be recorded before a student exists;
pass --student <exptid> later to drive with the distilled student instead
(then the recorded distribution is the deployed one).

Run on the box, from extreme-parkour's scripts directory:
  cd ~/extreme-parkour/legged_gym/legged_gym/scripts
  ~/bin/micromamba run -r ~/micromamba -n py38 python \\
      ~/snn_parkour_fpga/robot/isaac/record_event_frames.py \\
      --exptid 200-91-record --resume --resumeid 100-00-teacher --use_camera --delay \\
      --no_wandb --num_envs 8 --samples 64 --out ~/isaac_event_frames.npz
Samples are taken round-robin over environments at successive ticks after
a warm-up, so the set spans terrains and gait phases, not one instant.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isaacgym                                              # noqa: E402,F401
import torch                                                 # noqa: E402
from legged_gym import LEGGED_GYM_ROOT_DIR                   # noqa: E402
from legged_gym.envs import *                                # noqa: E402,F401,F403
from legged_gym.utils import get_args, task_registry         # noqa: E402

from fpga_event_backbone import FPGAEventBackbone            # noqa: E402


def _port_args():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--out", default=os.path.expanduser("~/isaac_event_frames.npz"))
    p.add_argument("--warmup_ticks", type=int, default=20, help="ticks before recording starts")
    p.add_argument("--side", type=int, default=64)
    p.add_argument("--student", default=None, help="exptid of a distilled student to drive the envs (else the teacher)")
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
    env_cfg.depth.resized = (ours.side, ours.side)
    env, env_cfg = task_registry.make_env(name=args.task, args=args, env_cfg=env_cfg)
    runner, _ = task_registry.make_alg_runner(log_root=log_pth, env=env, name=args.task,
                                              args=args, train_cfg=train_cfg)
    dev = runner.device
    bb = FPGAEventBackbone(env, window="repeat", binarise=True).to(dev)
    policy = runner.alg.actor_critic
    student = None
    if ours.student:
        ck = torch.load(os.path.join(LEGGED_GYM_ROOT_DIR, "logs", args.proj_name, ours.student,
                                     sorted(os.listdir(os.path.join(LEGGED_GYM_ROOT_DIR, "logs", args.proj_name, ours.student)))[-1]),
                        map_location=dev)
        runner.alg.depth_encoder.base_backbone = bb
        runner.alg.depth_encoder.load_state_dict(ck["depth_encoder_state_dict"])
        runner.alg.depth_actor.load_state_dict(ck["depth_actor_state_dict"])
        student = (runner.alg.depth_encoder.eval(), runner.alg.depth_actor.eval())

    obs = env.get_observations()
    infos = {"depth": env.depth_buffer.clone().to(dev)[:, -1]}
    frames, meta = [], []
    ticks = 0
    depth_latent = None
    with torch.no_grad():
        while len(frames) < ours.samples:
            if infos["depth"] is not None:
                ev = bb._events(infos["depth"].clone())              # (B, 2, H, W) 0/1, the tick frame
                if student is not None:
                    prop = obs[:, :env.cfg.env.n_proprio].clone(); prop[:, 6:8] = 0
                    lat_yaw = student[0](infos["depth"].clone(), prop)
                    depth_latent = lat_yaw[:, :-2]
                ticks += 1
                if ticks > ours.warmup_ticks:
                    b = (ticks - ours.warmup_ticks - 1) % ev.shape[0]   # round-robin over envs
                    frames.append(ev[b].cpu().numpy().astype(np.uint8))
                    meta.append((int(b), ticks, float(ev[b].mean())))
            if student is None:
                actions = policy.act_inference(obs, hist_encoding=True, scandots_latent=None)
            else:
                actions = student[1](obs, hist_encoding=True, scandots_latent=depth_latent)
            obs, _, _, _, infos = env.step(actions.detach())
            obs = obs.to(dev)
    arr = np.stack(frames)                                            # (N, 2, H, W)
    np.savez_compressed(ours.out, frames=arr, window="repeat", binarised=True,
                        far=bb.far, tick=bb.tick, side=ours.side,
                        driver=(ours.student or "teacher:" + args.resumeid),
                        meta=np.array(meta, dtype=np.float64))
    print("saved %s: %s, window=repeat, mean event-bit rate %.4f, %d ticks, driver %s"
          % (ours.out, arr.shape, arr.mean(), ticks, ours.student or "teacher"))


if __name__ == "__main__":
    main()
