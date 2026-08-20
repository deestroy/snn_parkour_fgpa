"""Checks for the cycle log: schema stability, ring behaviour, no-I/O
appends, flush round-trip, and the deadline stats. Run: python3 test_cycle_log.py"""
import os, sys, tempfile, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cycle_log import CycleLog, RECORD_DTYPE, deadline_stats

def main():
    # 1. schema: exact field list (drift = fail loudly, per the brief)
    names = [n for n in RECORD_DTYPE.names]
    assert names[:8] == ["cycle_index","t_camera_capture","t_preproc_done",
        "t_fpga_dispatch","t_fpga_return","t_policy_done","t_command_sent",
        "deadline_met"], names
    # 2. unknown key raises
    log = CycleLog(capacity=8)
    try:
        log.append({"not_a_field": 1}); raise AssertionError("should raise")
    except (KeyError, ValueError): pass
    # 3. ring wrap: 12 into capacity 8 -> 8 kept, oldest first, 4 dropped
    for i in range(12):
        log.append({"cycle_index": i, "t_command_sent": 100.0 + 0.02*i,
                    "deadline_met": (i % 5 != 0), "consecutive_misses": 0})
    r = log.records()
    assert len(r) == 8 and r["cycle_index"][0] == 4 and r["cycle_index"][-1] == 11
    assert log.dropped == 4
    # 4. append speed: must be safe inside a 20 ms loop (<<1 ms each)
    big = CycleLog()
    t0 = time.perf_counter()
    for i in range(5000):
        big.append({"cycle_index": i, "t_command_sent": i*0.02, "deadline_met": True})
    per = (time.perf_counter()-t0)/5000
    assert per < 200e-6, "append too slow: %.1f us" % (per*1e6)
    # 5. flush round-trip
    with tempfile.TemporaryDirectory() as d:
        p = big.flush(os.path.join(d, "trial1.npz"), meta={"variant": "dense"})
        z = np.load(p, allow_pickle=False)
        assert len(z["records"]) == 5000 and big.n_appended == 0
    # 6. stats: 1 miss in 5 -> 20 % rate; period 20 ms
    st = deadline_stats(r, 0.020)
    assert abs(st["miss_rate"] - 0.25) < 1e-9   # 8 kept: idx 4..11, misses at 5,10 -> 2/8
    assert abs(st["period_mean_ms"] - 20.0) < 1e-6
    print("CYCLE LOG TESTS PASS (append %.1f us)" % (per*1e6))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
