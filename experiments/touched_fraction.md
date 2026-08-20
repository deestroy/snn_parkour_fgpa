# C0031 — touched-neuron fraction, full test split (10000 samples, T=4)

Skippable in the sweep = neurons with I == 0 AND V == 0: at most
(1 - max(touched, alive)) of the sweep, per layer.

| layer | touched (I != 0) | alive (V != 0) | firing rate | sweep skippable (upper bound) |
|---|---|---|---|---|
| c1 | 0.3129 | 0.3990 | 0.0711 | 0.6010 |
| c2 | 0.4556 | 0.4909 | 0.0826 | 0.5091 |
| c3 | 0.6605 | 0.6898 | 0.1069 | 0.3102 |
| fc | 0.9984 | 0.9990 | 0.2910 | 0.0010 |
