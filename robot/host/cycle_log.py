"""Per-cycle control log: the schema from the year-two plan, defined ONCE.

Every control cycle appends one fixed-size record to a preallocated ring
buffer in memory; nothing is written to disk until flush() between trials,
so logging can never cause the deadline miss it is supposed to record.
This is the reference implementation and the schema's single source of
truth for year two -- the C/robot-side writer, when it exists, must match
it field for field (the header stores the dtype so a reader can verify).

Platform-agnostic: no robot SDK, no FPGA. Testable today (test_cycle_log.py).
"""

import json
import os
import time

import numpy as np

# The schema. Field names and meanings are the plan's, verbatim where
# possible. Times are float64 seconds on ONE clock (time.monotonic on the
# host; the power meter's samples must be aligned to the same clock at R3).
N_JOINTS = 12
N_LAYERS = 4          # c1, c2, c3, fc spike counts

RECORD_DTYPE = np.dtype([
    ("cycle_index",        np.int64),
    ("t_camera_capture",   np.float64),
    ("t_preproc_done",     np.float64),
    ("t_fpga_dispatch",    np.float64),
    ("t_fpga_return",      np.float64),
    ("t_policy_done",      np.float64),
    ("t_command_sent",     np.float64),
    ("deadline_met",       np.bool_),
    ("consecutive_misses", np.int32),
    ("stage_overrun_ms",   np.float32),   # worst stage's overrun; 0 if met
    ("overrun_stage",      np.int8),      # index into STAGES; -1 if met
    ("spike_counts",       np.int32, (N_LAYERS,)),
    ("energy_window_mJ",   np.float32),   # NaN until the meter is aligned
    ("joint_targets",      np.float32, (N_JOINTS,)),
    ("joint_pos",          np.float32, (N_JOINTS,)),
    ("joint_vel",          np.float32, (N_JOINTS,)),
    ("imu_quat",           np.float32, (4,)),
    ("imu_gyro",           np.float32, (3,)),
    ("policy_variant",     np.int8),      # 0 dense, 1 scatter, 2 ANN baseline
    ("perception_rate_hz", np.float32),
])
STAGES = ["camera", "preproc", "fpga", "policy", "command"]


class CycleLog:
    """Fixed-capacity ring buffer of RECORD_DTYPE records."""

    def __init__(self, capacity: int = 60 * 50 * 10):   # 10 min at 50 Hz
        self.buf = np.zeros(capacity, RECORD_DTYPE)
        self.capacity = capacity
        self.n_appended = 0            # total ever appended
        self.dropped = 0               # overwrites (ring wrapped unflushed)

    def append(self, rec: dict) -> None:
        """O(1), no allocation, no I/O. Unknown keys raise; missing keys
        keep the zero default (explicit is better, but a control loop must
        not die because a sensor field was absent for one tick)."""
        i = self.n_appended % self.capacity
        if self.n_appended >= self.capacity:
            self.dropped += 1
        row = self.buf[i]
        for k, v in rec.items():
            row[k] = v                 # raises on schema drift (ValueError)
        self.n_appended += 1

    def records(self) -> np.ndarray:
        """The valid records, oldest first."""
        n = min(self.n_appended, self.capacity)
        if self.n_appended <= self.capacity:
            return self.buf[:n].copy()
        s = self.n_appended % self.capacity
        return np.concatenate([self.buf[s:], self.buf[:s]])

    def flush(self, path: str, meta: dict = None) -> str:
        """Between trials only. Writes .npz (records + schema + meta) and
        resets the ring. Returns the path written."""
        recs = self.records()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        np.savez_compressed(
            path, records=recs,
            schema=json.dumps({"dtype": RECORD_DTYPE.descr, "stages": STAGES}),
            meta=json.dumps({**(meta or {}), "n_appended": self.n_appended,
                             "dropped": self.dropped,
                             "flushed_at": time.time()}))
        self.n_appended = 0
        self.dropped = 0
        return path


def deadline_stats(recs: np.ndarray, period_s: float):
    """The numbers R3/R7 report: miss rate, consecutive-miss max, and the
    jitter histogram source (command-to-command intervals)."""
    met = recs["deadline_met"]
    t = recs["t_command_sent"]
    dt = np.diff(t[t > 0])
    return {
        "cycles": int(len(recs)),
        "miss_rate": float(1.0 - met.mean()) if len(recs) else float("nan"),
        "max_consecutive_misses": int(recs["consecutive_misses"].max()) if len(recs) else 0,
        "period_mean_ms": float(dt.mean() * 1e3) if dt.size else float("nan"),
        "period_p99_ms": float(np.percentile(dt, 99) * 1e3) if dt.size else float("nan"),
        "period_max_ms": float(dt.max() * 1e3) if dt.size else float("nan"),
        "budget_ms": period_s * 1e3,
    }
