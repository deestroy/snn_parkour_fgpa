# ES-Parkour recreation - evaluation results

Level 3, 32 episodes/terrain.

## Success rates (cf. paper Fig. 5)

| Terrain | Teacher ANN | Student SNN |
|---|---|---|
| gap | 97% | 0% |
| step | 88% | 25% |
| hurdle | 94% | 0% |
| parkour | 53% | 0% |

## Joint motor energy per episode (cf. Table IV)

| Terrain | Teacher (J) | Student (J) |
|---|---|---|
| gap | 8101.7 | 2218.7 |
| step | 8740.3 | 6193.9 |
| hurdle | 8578.8 | 5307.8 |
| parkour | 7113.0 | 4060.2 |

## Operations & theoretical energy (cf. Tables II-III)

| Module | SNN FLOPs | SNN SOPs | ANN FLOPs | OPs(SNN):OPs(ANN) | SNN mJ | ANN mJ | Saving |
|---|---|---|---|---|---|---|---|
| encoder (0.06M) | 1.18e+06 | 6.41e+05 | 1.45e+08 | 0.01 : 1 | 0.006003 | 0.6663 | 99.1% |
| actor (0.23M) | 0 | 5.64e+04 | 2.32e+05 | 0.24 : 1 | 5.08e-05 | 0.001067 | 95.2% |
