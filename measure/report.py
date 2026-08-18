"""Report an M5 result the way the project brief demands: every metric together,
never mean power alone, and the measured number next to the tool's estimate
so the gap is a result in its own right.

Also writes the raw per-sample log to CSV so the plot and the number can be
regenerated, and so an examiner can see the idle/run/idle trace.
"""

import csv
import os
from typing import Optional

from measure.protocol import Result


def print_result(r: Result, vivado_estimate_uj: Optional[float],
                 resources: Optional[dict] = None,
                 firing_rates: Optional[dict] = None,
                 accuracy: Optional[float] = None) -> None:
    uj = r.energy_per_inf_j * 1e6
    uj_sem = r.energy_per_inf_sem_j * 1e6
    print("\n=== M5 result ===")
    print("energy per inference (measured) : %8.2f uJ  +/- %.2f (SEM)" % (uj, uj_sem))
    if vivado_estimate_uj is None:
        print("energy per inference (Vivado)   :      n/a  (fill in from the power report)")
    else:
        gap = uj / vivado_estimate_uj if vivado_estimate_uj else float("nan")
        print("energy per inference (Vivado)   : %8.2f uJ" % vivado_estimate_uj)
        print("measured / estimated            : %8.2fx   <- this ratio is a result" % gap)
    print("latency per inference           : %8.3f ms" % (r.latency_per_inf_s * 1e3))
    print("mean power, running             : %8.3f W   (idle %.3f W, delta %.3f W)"
          % (r.run.mean_w, 0.5 * (r.idle_before.mean_w + r.idle_after.mean_w), r.delta_w))
    print("total energy over run           : %8.2f J   (%d inferences in %.2fs)"
          % (r.total_energy_run_j, r.n_inferences, r.run.duration_s))
    print("idle drift before->after        : %+8.4f W   %s"
          % (r.idle_drift_w, "** DRIFT FLAG: exceeds threshold, rerun **" if r.drift_flag else "ok"))
    print("samples: idle %d + run %d + idle %d @ %.0f ms conversion"
          % (r.idle_before.n, r.run.n, r.idle_after.n, r.meter_conversion_s * 1e3))
    if resources:
        print("resources: " + "  ".join("%s=%s" % kv for kv in resources.items()))
    if firing_rates:
        print("firing rates: " + "  ".join("%s=%.1f%%" % (k, 100 * v) for k, v in firing_rates.items()))
    if accuracy is not None:
        print("task accuracy: %.2f%%" % (100 * accuracy))
    print("(report all of the above together; never mean power alone -- the project brief)")


def write_log_csv(protocol, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["phase", "t", "bus_v", "current_a", "power_w"])
        for row in protocol.log:
            w.writerow(row)
