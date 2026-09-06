# Pre-registration: dense P=4 first silicon pass (written 2026-09-06, before the measurement)

Written BEFORE the fixed build is on the board so the comparison cannot
be tuned after the fact (CLAUDE.md M7: "Do not tune the experiment to
produce a preferred answer").

Build under test: ENGINE=0, DENSE_P=4, BAKED_WEIGHTS=1, conv_layer_p_c1
regenerated from the single-stage-init conv_layer_p (weights read
directly from wrom_all at per-lane stepped addresses; per-lane obits
banks; flattened word gather). Server build 4.

## Predictions

1. Correctness: 16/16 N-MNIST check samples bit-identical (the all-zero
   result of the 09:52 build was the two-stage weight init, not the
   engine logic; the fixed RTL is bit-identical in simulation on
   c1/c2/c3 at P=1 and P=4 and on the robot geometry).
2. Engine-only latency (build 4 words 8..9): **~1.04 ms per inference**
   (104,059 cycles at 100 MHz incl. ~2k wrapper cycles), on every sample.
3. Spread across the 16 samples: **near zero** — the dense walk visits
   every neuron and synapse regardless of input, so latency is data-
   independent by construction. Any spread beyond a few microseconds
   would be DMA/host jitter, not the engine. (ED K=4 measured 554.8 to
   815.8 us on the same samples: a 1.47x spread.)
4. Matched-parallelism verdict on C1: ED K=4 (688.5 us mean) beats dense
   P=4 by **~1.5x** (sim: 1.54x). Per-sample, ED wins on every one of the
   16 (its worst, 815.8 us, is still below 1.04 ms).
5. Server overhead: ~117.5 us per pass, same as ED (same server, same
   -O0 CRC loop) — unless the app was rebuilt at -O2, in which case it
   drops for both engines equally.

## What would falsify

- Any CRC mismatch: an engine bug that simulation did not see (would
  trigger the same sim-vs-synthesis review as today).
- Latency more than ~3 % off 1.04 ms: a cycle-model error in the P-wide
  dense walk (taps+3 per neuron group, C0028 discipline applies).
- A spread comparable to ED's: something data-dependent leaked into the
  dense path (it must not).
