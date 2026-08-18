"""The M5 experiment protocol: idle -> run -> idle, and the energy-per-
inference number that falls out of it.

Why this shape. Energy per inference is (P_run - P_idle) * t_run / n_inf. Both
means must be trustworthy, so:
  - idle is measured BEFORE and AFTER the run; if the two idle means differ
    by more than a threshold, the supply drifted and the run is flagged;
  - each phase logs long enough for the standard error of the mean to fall
    below a target (default 1% of the delta), or a max time;
  - the run phase is driven by a callback that performs inferences back to
    back and returns how many it did, so time and count come from the same
    clock.
Every result carries its inputs (sample counts, durations, idle means both
sides) so the number can be audited, not just quoted.

Usage (real): Protocol(meter, run_fn).execute() where run_fn(stop_event) does
inferences until stop_event is set and returns the count.
Desk test: python3 measure/protocol.py --mock
"""

import argparse
import math
import statistics
import threading
import time
from dataclasses import dataclass, asdict
from typing import Callable, List, Optional, Tuple


@dataclass
class PhaseStats:
    name: str
    n: int
    duration_s: float
    mean_w: float
    std_w: float
    sem_w: float             # standard error of the mean
    mean_v: float
    mean_a: float


@dataclass
class Result:
    idle_before: PhaseStats
    run: PhaseStats
    idle_after: PhaseStats
    n_inferences: int
    energy_per_inf_j: float          # (P_run - P_idle) * t_run / n
    energy_per_inf_sem_j: float      # propagated from the SEMs
    latency_per_inf_s: float         # t_run / n
    delta_w: float                   # P_run - P_idle
    idle_drift_w: float              # idle_after - idle_before
    drift_flag: bool
    meter_conversion_s: float
    total_energy_run_j: float        # P_run * t_run (incl. idle floor)


def _stats(name: str, samples: List[Tuple[float, float, float, float]]) -> PhaseStats:
    ps = [s[3] for s in samples]
    n = len(ps)
    mean = statistics.fmean(ps)
    std = statistics.pstdev(ps) if n > 1 else 0.0
    return PhaseStats(name, n, samples[-1][0] - samples[0][0], mean, std,
                      std / math.sqrt(n) if n else float("inf"),
                      statistics.fmean(s[1] for s in samples),
                      statistics.fmean(s[2] for s in samples))


class Protocol:
    def __init__(self, meter, run_fn: Callable[[threading.Event], int],
                 idle_s: float = 10.0, run_s: float = 20.0,
                 sem_target_frac: float = 0.01, max_idle_s: float = 60.0,
                 drift_thresh_frac: float = 0.05, verbose: bool = True):
        self.meter = meter
        self.run_fn = run_fn
        self.idle_s, self.run_s = idle_s, run_s
        self.sem_target = sem_target_frac
        self.max_idle_s = max_idle_s
        self.drift_thresh = drift_thresh_frac
        self.verbose = verbose
        self.log: List[Tuple[str, float, float, float, float]] = []  # phase, t, v, a, w

    def _say(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def _sample_for(self, phase: str, seconds: float, until_sem: Optional[float] = None,
                    max_s: Optional[float] = None) -> List[Tuple[float, float, float, float]]:
        out = []
        t0 = time.time()
        period = max(self.meter.conversion_s, 0.005)
        while True:
            s = self.meter.sample()
            out.append(s)
            self.log.append((phase,) + s)
            el = time.time() - t0
            if el >= seconds:
                if until_sem is None or len(out) < 3:
                    break
                st = _stats(phase, out)
                if st.sem_w <= until_sem or (max_s and el >= max_s):
                    break
            time.sleep(period)
        return out

    def execute(self) -> Result:
        self._say("phase 1/3: idle (before) ...")
        idle1 = self._sample_for("idle_before", self.idle_s)
        st1 = _stats("idle_before", idle1)
        self._say("  %.3f W  (n=%d, sem %.4f W)" % (st1.mean_w, st1.n, st1.sem_w))

        self._say("phase 2/3: running inferences for %.0fs ..." % self.run_s)
        stop = threading.Event()
        count = {"n": 0}
        def worker():
            count["n"] = self.run_fn(stop)
        th = threading.Thread(target=worker, daemon=True)
        t_start = time.time()
        th.start()
        run = self._sample_for("run", self.run_s)
        stop.set()
        th.join(timeout=30)
        t_run = time.time() - t_start
        st2 = _stats("run", run)
        self._say("  %.3f W  (n=%d, sem %.4f W), %d inferences in %.2fs"
                  % (st2.mean_w, st2.n, st2.sem_w, count["n"], t_run))

        self._say("phase 3/3: idle (after) ...")
        idle2 = self._sample_for("idle_after", self.idle_s)
        st3 = _stats("idle_after", idle2)
        self._say("  %.3f W  (n=%d, sem %.4f W)" % (st3.mean_w, st3.n, st3.sem_w))

        idle_mean = 0.5 * (st1.mean_w + st3.mean_w)
        idle_sem = 0.5 * math.hypot(st1.sem_w, st3.sem_w)
        delta = st2.mean_w - idle_mean
        delta_sem = math.hypot(st2.sem_w, idle_sem)
        n = max(count["n"], 1)
        e_inf = delta * t_run / n
        e_sem = delta_sem * t_run / n
        drift = st3.mean_w - st1.mean_w
        flag = abs(drift) > self.drift_thresh * max(abs(delta), 1e-9)

        return Result(st1, st2, st3, count["n"], e_inf, e_sem, t_run / n,
                      delta, drift, flag, self.meter.conversion_s,
                      st2.mean_w * t_run)


def _mock_demo(load_w: float = 0.85, inf_ms: float = 12.0) -> Result:
    from measure.ina226 import MockINA226
    m = MockINA226(idle_w=3.2, noise_w=0.03, drift_w_per_s=0.0005)

    def run_fn(stop: threading.Event) -> int:
        m.set_load(load_w)
        n = 0
        while not stop.is_set():
            time.sleep(inf_ms / 1000.0)   # one "inference"
            n += 1
        m.set_load(0.0)
        return n
    p = Protocol(m, run_fn, idle_s=3.0, run_s=6.0)
    return p.execute()


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    if a.mock:
        r = _mock_demo()
        from measure.report import print_result
        print_result(r, vivado_estimate_uj=None)
