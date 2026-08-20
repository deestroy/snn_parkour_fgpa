"""S1: the perception-budget mechanism (the year-two plan's core rule).

In a simulator, physics waits — a slow perception path would silently make
every deadline. This loop makes deadlines REAL again:

  - the sim advances in lockstep at the control rate;
  - on each perception tick, the perception function is called and its
    WALL-CLOCK time is measured (never modelled);
  - if it fits the budget, the fresh latent is used from the correct tick;
  - if it does not, the policy runs with the STALE latent from the previous
    tick — exactly what a real robot would do — and the miss is logged
    (stage, overrun) in the per-cycle record;
  - after `escalate_after` consecutive misses the trial is FLAGGED (the
    physical analogue was damping mode); it keeps logging, never lies.

The perception function is pluggable: golden model, FPGA-over-UART, or a
delay-injecting fake (the test). The sim step is pluggable the same way,
so this file has no dependency on MuJoCo and is fully testable on any host.

Check: python3 robot/host/test_perception_loop.py
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

try:
    from .cycle_log import CycleLog
except ImportError:                      # direct script use
    from cycle_log import CycleLog


@dataclass
class LoopConfig:
    control_rate_hz: float = 50.0
    perception_rate_hz: float = 10.0     # sweep parameter (R7/S5)
    # budget for the whole perception path per perception tick; None means
    # one perception period (the natural deadline)
    budget_s: Optional[float] = None
    escalate_after: int = 5              # consecutive misses -> trial flagged
    variant: int = 1                     # 0 dense, 1 scatter, 2 sw baseline

    def resolved_budget(self) -> float:
        return self.budget_s if self.budget_s is not None \
            else 1.0 / self.perception_rate_hz


@dataclass
class LoopState:
    latent: np.ndarray = None            # what the policy actually sees
    latent_age_ticks: int = 0            # 0 = fresh this perception tick
    consecutive_misses: int = 0
    trial_flagged: bool = False
    flagged_at_cycle: int = -1
    cycles: int = 0
    spike_counts: np.ndarray = field(
        default_factory=lambda: np.zeros(4, np.int32))


class PerceptionLoop:
    """Drives sim_step at the control rate and perceive at the perception
    rate, charging perceive's wall time against the budget."""

    def __init__(self, cfg: LoopConfig, log: CycleLog,
                 perceive: Callable[[np.ndarray], np.ndarray],
                 sim_step: Callable[[np.ndarray], dict],
                 policy: Callable[[dict, np.ndarray], np.ndarray],
                 clock: Callable[[], float] = time.monotonic):
        self.cfg = cfg
        self.log = log
        self.perceive = perceive
        self.sim_step = sim_step
        self.policy = policy
        self.clock = clock
        self.st = LoopState()
        self.every = max(1, round(cfg.control_rate_hz / cfg.perception_rate_hz))

    def run(self, n_cycles: int, first_obs: dict) -> LoopState:
        st, cfg = self.st, self.cfg
        budget = cfg.resolved_budget()
        obs = first_obs
        for _ in range(n_cycles):
            rec = {"cycle_index": st.cycles,
                   "policy_variant": cfg.variant,
                   "perception_rate_hz": cfg.perception_rate_hz}
            perception_tick = (st.cycles % self.every == 0)
            met = True
            overrun = 0.0
            if perception_tick:
                t0 = self.clock()
                rec["t_camera_capture"] = t0
                fresh = self.perceive(obs.get("events"))
                t1 = self.clock()
                rec["t_fpga_dispatch"] = t0
                rec["t_fpga_return"] = t1
                elapsed = t1 - t0
                if elapsed <= budget:
                    st.latent = fresh
                    st.latent_age_ticks = 0
                else:                     # MISS: policy sees the stale latent
                    met = False
                    overrun = (elapsed - budget) * 1e3
                    st.latent_age_ticks += 1
                    if st.latent is None:      # very first tick missed:
                        st.latent = np.zeros_like(fresh)
                # NOTE: `fresh` is computed either way (the wall clock does
                # not stop); on a miss it is discarded, as on a real robot
                # where the late result describes an old world.
            if st.latent is not None:
                st.latent_age_ticks += 0  # age accounting is per perception tick
            act = self.policy(obs, st.latent)
            rec["t_policy_done"] = self.clock()
            obs = self.sim_step(act)
            rec["t_command_sent"] = self.clock()
            rec["deadline_met"] = met
            if not met:
                st.consecutive_misses += 1
                rec["stage_overrun_ms"] = overrun
                rec["overrun_stage"] = 2       # fpga stage
                if (st.consecutive_misses >= cfg.escalate_after
                        and not st.trial_flagged):
                    st.trial_flagged = True
                    st.flagged_at_cycle = st.cycles
            elif perception_tick:
                st.consecutive_misses = 0
            rec["consecutive_misses"] = st.consecutive_misses
            self.log.append(rec)
            st.cycles += 1
        return st
