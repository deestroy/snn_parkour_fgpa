"""One GIF per parkour terrain of the robot COMPLETING the course (all 8
waypoints reached before the time limit), for the teacher, their stock
depth student, or our FPGA event student. Headless: a follow camera is
attached to every environment and read back each control step; episodes
that fall or time out are discarded, and the first successful episode on
each terrain type is written at 25 fps.

Run on the box from extreme-parkour's scripts directory:
  python record_gifs.py --exptid 300-10-gifs --resume --resumeid 100-00-teacher --no_wandb
      --policy teacher --num_envs 32 --out ~/gifs
Options: --policy student|fpga (--fpga_run <exptid>), --width 480, --every 2,
         --max_steps 6000, --side_view for a pure side camera.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import isaacgym                                              # noqa: E402,F401
from isaacgym import gymapi                                  # noqa: E402
import torch                                                 # noqa: E402
from legged_gym import LEGGED_GYM_ROOT_DIR                   # noqa: E402
from legged_gym.envs import *                                # noqa: E402,F401,F403
from legged_gym.utils import get_args, task_registry         # noqa: E402

from eval_tally import TERRAIN_NAMES                         # noqa: E402
from fpga_event_backbone import FPGAEventBackbone            # noqa: E402

WANTED = {15: "parkour", 16: "hurdle", 18: "step", 19: "gap"}


def _port_args():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--policy", choices=("teacher", "student", "fpga"), default="teacher")
    p.add_argument("--fpga_run", default=None)
    p.add_argument("--window", choices=("repeat", "consecutive"), default="repeat")
    p.add_argument("--out", default=os.path.expanduser("~/gifs"))
    p.add_argument("--width", type=int, default=480)
    p.add_argument("--every", type=int, default=2, help="keep every n-th control step (50 Hz / n fps)")
    p.add_argument("--max_steps", type=int, default=6000)
    p.add_argument("--side", type=int, default=64)
    p.add_argument("--side_view", action="store_true")
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
    os.makedirs(log_pth, exist_ok=True); os.makedirs(ours.out, exist_ok=True)
    env_cfg, train_cfg = task_registry.get_cfgs(name=args.task)
    n_envs = args.num_envs or 32
    env_cfg.env.num_envs = n_envs
    env_cfg.env.episode_length_s = 20
    env_cfg.commands.resampling_time = 60
    env_cfg.terrain.num_rows = 2
    env_cfg.terrain.num_cols = max(4, n_envs // 2)
    env_cfg.terrain.height = [0.02, 0.02]
    d = {k: 0.0 for k in env_cfg.terrain.terrain_dict}
    for k in ("parkour", "parkour_hurdle", "parkour_step", "parkour_gap"):
        d[k] = 0.25
    env_cfg.terrain.terrain_dict = d
    env_cfg.terrain.terrain_proportions = list(d.values())
    env_cfg.terrain.curriculum = False
    env_cfg.terrain.max_difficulty = False
    env_cfg.depth.angle = [0, 1]
    env_cfg.noise.add_noise = True
    env_cfg.domain_rand.randomize_friction = True
    env_cfg.domain_rand.push_robots = False        # a clean run for the picture
    env_cfg.domain_rand.randomize_base_mass = False
    env_cfg.domain_rand.randomize_base_com = False
    if ours.policy == "fpga":
        env_cfg.depth.resized = (ours.side, ours.side)
    args.num_envs = n_envs

    env, env_cfg = task_registry.make_env(name=args.task, args=args, env_cfg=env_cfg)
    train_cfg.runner.resume = True
    runner, train_cfg = task_registry.make_alg_runner(log_root=log_pth, env=env, name=args.task,
                                                      args=args, train_cfg=train_cfg)
    dev = env.device
    alg = runner.alg
    depth_encoder = depth_actor = None
    if ours.policy == "fpga":
        alg.depth_encoder.base_backbone = FPGAEventBackbone(env, window=ours.window).to(dev)
        ck = torch.load(_latest_ckpt(ours.fpga_run, args.proj_name), map_location=dev)
        alg.depth_encoder.load_state_dict(ck["depth_encoder_state_dict"])
        alg.depth_actor.load_state_dict(ck["depth_actor_state_dict"])
    if ours.policy != "teacher":
        depth_encoder = alg.depth_encoder.eval(); depth_actor = alg.depth_actor.eval()
    policy = runner.get_inference_policy(device=dev)

    # --- one follow camera per environment ------------------------------------
    gym, sim = env.gym, env.sim
    props = gymapi.CameraProperties()
    props.width, props.height = ours.width, int(round(ours.width * 9 / 16))
    cams = [gym.create_camera_sensor(env.envs[i], props) for i in range(env.num_envs)]
    offset = np.array([0.0, 2.2, 0.9]) if ours.side_view else np.array([-1.6, 1.6, 0.9])

    def aim(i):
        root = env.root_states[i, :3].cpu().numpy()
        gym.set_camera_location(cams[i], env.envs[i], gymapi.Vec3(*(root + offset)),
                                gymapi.Vec3(*(root + np.array([0.4, 0.0, 0.0]))))

    def grab(i):
        img = gym.get_camera_image(sim, env.envs[i], cams[i], gymapi.IMAGE_COLOR)
        return np.frombuffer(img, dtype=np.uint8).reshape(props.height, props.width, 4)[:, :, :3].copy()

    classes = env.env_class.long().cpu().numpy()
    present = sorted(set(int(c) for c in classes) & set(WANTED))
    print("terrains present among %d envs: %s" % (env.num_envs, [WANTED[c] for c in present]), flush=True)
    need = set(present)
    buffers = {i: [] for i in range(env.num_envs)}
    saved = {}
    obs = env.get_observations()
    infos = {"depth": env.depth_buffer.clone().to(dev)[:, -1] if runner.if_depth else None}
    depth_latent = yaw = None
    step = 0
    with torch.no_grad():
        while need and step < ours.max_steps:
            if depth_encoder is not None:
                if infos["depth"] is not None:
                    o = obs[:, :env.cfg.env.n_proprio].clone(); o[:, 6:8] = 0
                    ly = depth_encoder(infos["depth"].clone(), o)
                    depth_latent, yaw = ly[:, :-2], ly[:, -2:]
                obs[:, 6:8] = 1.5 * yaw
                actions = depth_actor(obs.detach(), hist_encoding=True, scandots_latent=depth_latent)
            else:
                actions = policy(obs.detach(), hist_encoding=True, scandots_latent=None)
            pre_len = env.episode_length_buf.clone()
            obs, _, _, dones, infos = env.step(actions.detach())
            # render the follow cameras (the env only does this for its depth cameras)
            gym.step_graphics(sim); gym.render_all_camera_sensors(sim)
            active = [i for i in range(env.num_envs) if int(classes[i]) in need]
            if step % ours.every == 0:
                for i in active:
                    aim(i); buffers[i].append(grab(i))
            done = (dones > 0).cpu().numpy(); tout = infos["time_outs"].cpu().numpy()
            for i in active:
                if not done[i]:
                    continue
                success = bool(tout[i]) and int(pre_len[i]) + 1 <= int(env.max_episode_length)
                c = int(classes[i])
                if success and c in need and len(buffers[i]) > 20:
                    from PIL import Image
                    frames = [Image.fromarray(f) for f in buffers[i]]
                    path = os.path.join(ours.out, "%s_%s.gif" % (ours.policy, WANTED[c]))
                    frames[0].save(path, save_all=True, append_images=frames[1:],
                                   duration=int(1000 * ours.every / 50), loop=0, optimize=True)
                    saved[WANTED[c]] = (path, len(frames), int(pre_len[i]) + 1)
                    need.discard(c)
                    print("saved %s: %d frames, episode %d steps (%.1f s)" % (path, len(frames), int(pre_len[i]) + 1, (int(pre_len[i]) + 1) / 50), flush=True)
                buffers[i] = []
            step += 1
    missing = [WANTED[c] for c in need]
    print("done at step %d: saved %s; missing %s" % (step, sorted(saved), missing), flush=True)
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
