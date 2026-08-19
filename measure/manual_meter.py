"""Manual-entry M5 measurement with a bench multimeter (measure/dmm_protocol.md).

Prompts for idle-before / burst / idle-after current readings, the supply
voltage, and the burst's N and elapsed seconds (from uart_client.py), then
computes energy per inference with an uncertainty from the readings'
spread and writes a JSON record. Numbers are entered, not measured, by
this script -- it is a form with arithmetic, so the first meter session is
not improvised.

Run:  python3 measure/manual_meter.py --label ed_k4
      python3 measure/manual_meter.py --selftest      (no prompts)
"""

import argparse
import json
import math
import os
import statistics
import time

RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")


def _floats(prompt):
    while True:
        s = input(prompt).strip()
        try:
            v = [float(x) for x in s.replace(",", " ").split()]
            if v:
                return v
        except ValueError:
            pass
        print("  enter one or more numbers separated by spaces")


def compute(v_supply, i_idle_before, i_run, i_idle_after, n_inf, elapsed_s,
            vivado_est_uj=None):
    def st(x):
        m = statistics.fmean(x)
        sd = statistics.pstdev(x) if len(x) > 1 else 0.0
        return m, sd / math.sqrt(len(x))
    ib, ib_sem = st(i_idle_before)
    ia, ia_sem = st(i_idle_after)
    ir, ir_sem = st(i_run)
    i_idle = 0.5 * (ib + ia)
    i_idle_sem = 0.5 * math.hypot(ib_sem, ia_sem)
    delta_a = ir - i_idle
    delta_sem = math.hypot(ir_sem, i_idle_sem)
    delta_w = v_supply * delta_a
    e_j = delta_w * elapsed_s / n_inf
    e_sem = v_supply * delta_sem * elapsed_s / n_inf
    drift = ia - ib
    return {
        "v_supply": v_supply, "i_idle_before_a": ib, "i_idle_after_a": ia, "i_run_a": ir,
        "delta_a": delta_a, "delta_w": delta_w, "delta_w_sem": v_supply * delta_sem,
        "idle_drift_a": drift,
        "drift_flag": abs(drift) > max(abs(delta_a), 1e-9),
        "resolvable": abs(delta_a) > 3 * delta_sem,
        "n_inferences": n_inf, "elapsed_s": elapsed_s,
        "latency_per_inf_ms": 1e3 * elapsed_s / n_inf,
        "energy_per_inf_uj": 1e6 * e_j, "energy_per_inf_uj_sem": 1e6 * e_sem,
        "power_idle_w": v_supply * i_idle, "power_run_w": v_supply * ir,
        "vivado_estimate_uj": vivado_est_uj,
        "measured_over_estimate": (1e6 * e_j / vivado_est_uj) if vivado_est_uj else None,
    }


def report(r):
    print("\n=== M5 result (DMM, manual entry) ===")
    print("energy per inference (measured) : %8.2f uJ  +/- %.2f (SEM)%s"
          % (r["energy_per_inf_uj"], r["energy_per_inf_uj_sem"],
             "" if r["resolvable"] else "   ** delta NOT resolved above noise (<3 SEM) **"))
    if r["vivado_estimate_uj"]:
        print("energy per inference (Vivado)   : %8.2f uJ   measured/estimated = %.2fx"
              % (r["vivado_estimate_uj"], r["measured_over_estimate"]))
    print("latency per inference           : %8.3f ms" % r["latency_per_inf_ms"])
    print("power idle / run / delta        : %.3f W / %.3f W / %+.4f W (+/- %.4f)"
          % (r["power_idle_w"], r["power_run_w"], r["delta_w"], r["delta_w_sem"]))
    print("idle drift before->after        : %+.4f A  %s"
          % (r["idle_drift_a"], "** exceeds the delta: rerun **" if r["drift_flag"] else "ok"))


def selftest():
    r = compute(12.0, [0.5120, 0.5121, 0.5119, 0.5120, 0.5121],
                [0.5158, 0.5160, 0.5157, 0.5159, 0.5158],
                [0.5121, 0.5120, 0.5122, 0.5120, 0.5121], 12000, 18.17, vivado_est_uj=None)
    report(r)
    # 3.8 mA at 12 V = 45.6 mW over 18.17 s / 12000 = 69 uJ; must be resolvable, no drift
    ok = abs(r["energy_per_inf_uj"] - 69.0) < 1.0 and r["resolvable"] and not r["drift_flag"]
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--vivado-uj", type=float, default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    print("Readings in AMPS (e.g. 0.5121). Several per phase, space-separated.")
    v = _floats("supply voltage at the barrel (V): ")[0]
    ib = _floats("idle BEFORE, currents (A): ")
    ir = _floats("during BURST, currents (A): ")
    ia = _floats("idle AFTER, currents (A): ")
    n = int(_floats("burst N (iterations, from uart_client): ")[0])
    el = _floats("burst elapsed seconds (from uart_client): ")[0]
    r = compute(v, ib, ir, ia, n, el, a.vivado_uj)
    r.update({"label": a.label, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "readings": {"idle_before": ib, "run": ir, "idle_after": ia}})
    report(r)
    os.makedirs(RUNS, exist_ok=True)
    path = os.path.join(RUNS, "%s_%s.json" % (time.strftime("%Y%m%d_%H%M%S"), a.label))
    with open(path, "w") as fh:
        json.dump(r, fh, indent=2)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
