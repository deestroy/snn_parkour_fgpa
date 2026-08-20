"""S1 done-when: injected delays must produce EXACTLY the predicted miss
pattern in the log — no silent waiting, stale latents on misses, escalation
flag at the configured threshold. Uses a fake clock so the test is exact
and instant (the wall-clock path is the same code either way).

Run: python3 robot/host/test_perception_loop.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cycle_log import CycleLog, deadline_stats
from perception_loop import LoopConfig, PerceptionLoop


class FakeClock:
    """Advances only when told: perceive() charges exactly the scripted
    delay, everything else is free. Makes miss patterns exact."""
    def __init__(self):
        self.t = 100.0
    def __call__(self):
        return self.t


def run_with_delays(delays_s, cfg=None):
    cfg = cfg or LoopConfig(control_rate_hz=50, perception_rate_hz=10,
                            escalate_after=3)
    clock = FakeClock()
    log = CycleLog(capacity=4096)
    seq = {"i": -1}
    latents_seen = []

    def perceive(events):
        seq["i"] += 1
        clock.t += delays_s[seq["i"] % len(delays_s)]
        return np.full(32, float(seq["i"]))     # latent k on tick k

    def policy(obs, latent):
        latents_seen.append(-1.0 if latent is None else float(latent[0]))
        return np.zeros(12)

    def sim_step(act):
        clock.t += 1e-6
        return {"events": np.zeros((2, 8, 8))}

    loop = PerceptionLoop(cfg, log, perceive, sim_step, policy, clock=clock)
    st = loop.run(n_cycles=50, first_obs={"events": np.zeros((2, 8, 8))})
    return st, log, latents_seen


def main() -> int:
    budget = 0.1                     # 10 Hz perception -> 100 ms budget
    # ticks:      0     1     2     3     4     5     6     7     8     9
    delays = [0.010, 0.150, 0.020, 0.200, 0.300, 0.250, 0.030, 0.010, 0.500, 0.020]
    st, log, seen = run_with_delays(delays)
    recs = log.records()
    # 50 control cycles at every-5 -> 10 perception ticks; misses at scripted
    # delays > 0.1: ticks 1, 3, 4, 5, 8  -> 5 misses
    misses = (~recs["deadline_met"]).sum()
    assert misses == 5, f"expected 5 misses, got {misses}"
    # stale-latent rule: during tick 1's miss the policy must still see
    # latent 0; during the 3-4-5 miss run it must see latent 2 throughout
    per_tick_first_seen = seen[::5]
    assert per_tick_first_seen[1] == 0.0, per_tick_first_seen
    assert per_tick_first_seen[3] == 2.0 and per_tick_first_seen[4] == 2.0 \
        and per_tick_first_seen[5] == 2.0, per_tick_first_seen
    # fresh again on tick 6
    assert per_tick_first_seen[6] == 6.0, per_tick_first_seen
    # escalation: 3 consecutive (ticks 3,4,5) -> flagged exactly then
    assert st.trial_flagged and st.flagged_at_cycle == 25, st.flagged_at_cycle
    # overruns logged with the right magnitude (tick 3: 200-100 = 100 ms)
    over = recs["stage_overrun_ms"][~recs["deadline_met"]]
    assert abs(over[1] - 100.0) < 1e-6, over
    # no silent waiting: t_command_sent advances every cycle
    t = recs["t_command_sent"]
    assert (np.diff(t) > 0).all()
    # stats sanity
    stats = deadline_stats(recs, 0.02)
    assert abs(stats["miss_rate"] - 5 / 50) < 1e-9
    # all-fast control: zero misses
    st2, log2, _ = run_with_delays([0.010])
    assert (~log2.records()["deadline_met"]).sum() == 0 and not st2.trial_flagged
    # first-tick miss: policy sees a ZERO latent, not a crash
    st3, log3, seen3 = run_with_delays([0.500, 0.010])
    assert seen3[0] == 0.0 and not log3.records()["deadline_met"][0]
    print("PERCEPTION LOOP TESTS PASS (5 scripted misses, stale latents, "
          "escalation at cycle 25, no silent waits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
