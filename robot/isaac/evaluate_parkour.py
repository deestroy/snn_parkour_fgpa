"""Success rate per parkour terrain, the paper's Fig. 5 quantity, for the
teacher, extreme-parkour's stock depth student, or our FPGA event student,
under ONE protocol (their evaluate.py's: 256 envs, 20 s episodes, the four
parkour terrains at equal share, random difficulty, noise + friction
randomisation + pushes on, no curriculum).

  --policy teacher                 scandots teacher (no camera); --resumeid <teacher exptid>
  --policy student                 their depth student; --use_camera --resumeid <student exptid>
  --policy fpga --fpga_run <exptid>  ours: --use_camera --resumeid <teacher exptid> (actor
                                   weights come from the teacher checkpoint's actor, then the
                                   FPGA run's depth_encoder/depth_actor state dicts are loaded)

Run on the box from extreme-parkour's scripts directory (see README):
  python evaluate_parkour.py --exptid 300-00-eval --resume --resumeid 100-00-teacher
      --no_wandb --policy teacher --steps 1500 --out ~/eval_teacher.json
Writes a markdown table to stdout and a JSON summary to --out.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isaacgym                                              # noqa: E402,F401
import torch                                                 # noqa: E402
from legged_gym import LEGGED_GYM_ROOT_DIR                   # noqa: E402
from legged_gym.envs import *                                # noqa: E402,F401,F403
from legged_gym.utils import get_args, task_registry         # noqa: E402

from eval_tally import EpisodeTally                          # noqa: E402
from fpga_event_backbone import FPGAEventBackbone            # noqa: E402


def _port_args():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--policy", choices=("teacher", "student", "fpga"), default="teacher")
    p.add_argument("--fpga_run", default=None, help="exptid of the FPGA-student distillation run")
    p.add_argument("--window", choices=("repeat", "consecutive"), default="repeat")
    p.add_argument("--steps", type=int, default=1500)
    p.add_argument("--side", type=int, default=64)
    p.add_argument("--max_difficulty", action="store_true")
    p.add_argument("--out", default=None)
    ours, rest = p.parse_known_args()
    sys.argv = [sys.argv[0]] + rest
    return ours


def _latest_ckpt(exptid, proj):
    d = os.path.join(LEGGED_GYM_ROOT_DIR, "logs", proj, exptid)
    models = sorted([f for f in os.listdir(d) if f.startswith("model_")],
                    key=lambda m: int(m.split("_")[1].split(".")[0]))
    return os.path.join(d, models[-1])


def main():
    ours = _port_args()
    args = get_args()
    args.headless = True
    if ours.policy != "teacher":
        args.use_camera = True
    log_pth = os.path.join(LEGGED_GYM_ROOT_DIR, "logs", args.proj_name, args.exptid)
    os.makedirs(log_pth, exist_ok=True)
    env_cfg, train_cfg = task_registry.get_cfgs(name=args.task)
    # --- their evaluate.py protocol -------------------------------------------
    env_cfg.env.num_envs = 256
    env_cfg.env.episode_length_s = 20
    env_cfg.commands.resampling_time = 60
    env_cfg.terrain.num_rows = 5
    env_cfg.terrain.num_cols = 5
    env_cfg.terrain.height = [0.02, 0.02]
    d = {k: 0.0 for k in env_cfg.terrain.terrain_dict}
    for k in ("parkour", "parkour_hurdle", "parkour_step", "parkour_gap"):
        d[k] = 0.25
    env_cfg.terrain.terrain_dict = d
    env_cfg.terrain.terrain_proportions = list(d.values())
    env_cfg.terrain.curriculum = False
    env_cfg.terrain.max_difficulty = ours.max_difficulty
    env_cfg.depth.angle = [0, 1]
    env_cfg.noise.add_noise = True
    env_cfg.domain_rand.randomize_friction = True
    env_cfg.domain_rand.push_robots = True
    env_cfg.domain_rand.push_interval_s = 6
    env_cfg.domain_rand.randomize_base_mass = False
    env_cfg.domain_rand.randomize_base_com = False
    if ours.policy == "fpga":
        env_cfg.depth.resized = (ours.side, ours.side)
    if args.num_envs is not None:
        env_cfg.env.num_envs = args.num_envs

    env, env_cfg = task_registry.make_env(name=args.task, args=args, env_cfg=env_cfg)
    train_cfg.runner.resume = True
    runner, train_cfg = task_registry.make_alg_runner(log_root=log_pth, env=env, name=args.task,
                                                      args=args, train_cfg=train_cfg)
    dev = env.device
    alg = runner.alg
    depth_encoder = depth_actor = None
    if ours.policy == "fpga":
        assert ours.fpga_run, "--fpga_run <exptid> required"
        alg.depth_encoder.base_backbone = FPGAEventBackbone(env, window=ours.window).to(dev)
        ck = torch.load(_latest_ckpt(ours.fpga_run, args.proj_name), map_location=dev)
        alg.depth_encoder.load_state_dict(ck["depth_encoder_state_dict"])
        alg.depth_actor.load_state_dict(ck["depth_actor_state_dict"])
    if ours.policy != "teacher":
        depth_encoder = alg.depth_encoder.eval()
        depth_actor = alg.depth_actor.eval()
    policy = runner.get_inference_policy(device=dev)

    tally = EpisodeTally(env.num_envs, env_cfg.terrain.num_goals, int(env.max_episode_length), dev)
    obs = env.get_observations()
    infos = {"depth": env.depth_buffer.clone().to(dev)[:, -1] if runner.if_depth else None}
    depth_latent = None
    yaw = None
    with torch.no_grad():
        for _ in range(ours.steps):
            if depth_encoder is not None:
                if infos["depth"] is not None:
                    obs_student = obs[:, :env.cfg.env.n_proprio].clone()
                    obs_student[:, 6:8] = 0
                    lat_yaw = depth_encoder(infos["depth"].clone(), obs_student)
                    depth_latent, yaw = lat_yaw[:, :-2], lat_yaw[:, -2:]
                obs[:, 6:8] = 1.5 * yaw
                actions = depth_actor(obs.detach(), hist_encoding=True, scandots_latent=depth_latent)
            else:
                actions = policy(obs.detach(), hist_encoding=True, scandots_latent=None)
            tally.before_step(env.cur_goal_idx, env.episode_length_buf)
            obs, _, _, dones, infos = env.step(actions.detach())
            tally.after_step(dones, infos["time_outs"], env.env_class)
    print("policy=%s steps=%d envs=%d max_difficulty=%s" % (ours.policy, ours.steps, env.num_envs, ours.max_difficulty))
    print(tally.table())
    if ours.out:
        with open(ours.out, "w") as fh:
            json.dump({"policy": ours.policy, "run": ours.fpga_run or args.resumeid, "steps": ours.steps,
                       "num_envs": env.num_envs, "max_difficulty": ours.max_difficulty,
                       "window": ours.window if ours.policy == "fpga" else None,
                       "terrains": tally.summary()}, fh, indent=1)
        print("summary -> %s" % ours.out)


if __name__ == "__main__":
    main()
