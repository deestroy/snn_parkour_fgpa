"""Per-terrain episode accounting for the parkour evaluation (pure torch, no
IsaacGym, so test_port.py can check it).

Success = the episode ended because all `num_goals` waypoints were reached
(extreme-parkour folds that into `time_outs`; a real time-out has
pre-step episode length + 1 > max_episode_length, a goal-cutoff does not).
Fall = any other termination (roll/pitch/height cutoff). Waypoint fraction
= highest goal index reached / num_goals, as their evaluate.py reports it.
"""
import torch

TERRAIN_NAMES = {15: "parkour", 16: "hurdle", 18: "step", 19: "gap", 17: "flat"}


class EpisodeTally:
    def __init__(self, num_envs: int, num_goals: int, max_episode_length: int, device):
        self.num_goals = int(num_goals)
        self.max_len = int(max_episode_length)
        self.best_goal = torch.zeros(num_envs, dtype=torch.long, device=device)
        self.episodes = {}          # terrain idx -> [n, successes, falls, timeouts, waypoint_frac_sum, len_sum]

    def before_step(self, cur_goal_idx: torch.Tensor, episode_len: torch.Tensor):
        self.best_goal = torch.maximum(self.best_goal, cur_goal_idx)
        self._pre_len = episode_len.clone()

    def after_step(self, dones: torch.Tensor, time_outs: torch.Tensor, env_class: torch.Tensor):
        done = dones > 0
        if not bool(done.any()):
            return
        real_timeout = time_outs & (self._pre_len + 1 > self.max_len)
        success = time_outs & ~real_timeout
        fall = done & ~time_outs
        # the final goal increment lands in the terminating step: count it
        best = torch.where(success, torch.full_like(self.best_goal, self.num_goals), self.best_goal)
        for i in torch.nonzero(done).flatten().tolist():
            k = int(env_class[i])
            row = self.episodes.setdefault(k, [0, 0, 0, 0, 0.0, 0])
            row[0] += 1
            row[1] += int(success[i]); row[2] += int(fall[i]); row[3] += int(real_timeout[i])
            row[4] += float(best[i]) / self.num_goals
            row[5] += int(self._pre_len[i]) + 1
        self.best_goal[done] = 0

    def table(self) -> str:
        lines = ["| terrain | episodes | success | fall | time-out | waypoints reached | mean length (steps) |",
                 "|---|---|---|---|---|---|---|"]
        for k in sorted(self.episodes, key=lambda k: TERRAIN_NAMES.get(k, str(k))):
            n, s, f, t, wf, ln = self.episodes[k]
            lines.append("| %s | %d | %.1f %% | %.1f %% | %.1f %% | %.2f | %.0f |"
                         % (TERRAIN_NAMES.get(k, "idx%d" % k), n, 100 * s / n, 100 * f / n,
                            100 * t / n, wf / n, ln / n))
        return "\n".join(lines)

    def summary(self) -> dict:
        return {TERRAIN_NAMES.get(k, "idx%d" % k):
                {"episodes": v[0], "success_rate": v[1] / v[0], "fall_rate": v[2] / v[0],
                 "timeout_rate": v[3] / v[0], "waypoint_frac": v[4] / v[0], "mean_len": v[5] / v[0]}
                for k, v in self.episodes.items()}
