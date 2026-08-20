# ES-Parkour recreation - evaluation results

Level 6, 32 episodes/terrain.

## Success rates (cf. paper Fig. 5)

| Terrain | Teacher ANN | Student SNN |
|---|---|---|
| gap | 12% | 0% |
| step | 78% | 19% |
| hurdle | 94% | 0% |
| parkour | 0% | 0% |

## Joint motor energy per episode (cf. Table IV)

| Terrain | Teacher (J) | Student (J) |
|---|---|---|
| gap | 5233.4 | 1121.3 |
| step | 9618.6 | 7369.0 |
| hurdle | 9591.7 | 6706.1 |
| parkour | 1836.1 | 1391.4 |

## Operations & theoretical energy (cf. Tables II-III)

| Module | SNN FLOPs | SNN SOPs | ANN FLOPs | OPs(SNN):OPs(ANN) | SNN mJ | ANN mJ | Saving |
|---|---|---|---|---|---|---|---|
| encoder (0.06M) | 1.18e+06 | 4.97e+05 | 1.45e+08 | 0.01 : 1 | 0.005874 | 0.6663 | 99.1% |
| actor (0.23M) | 0 | 5.57e+04 | 2.32e+05 | 0.24 : 1 | 5.01e-05 | 0.001067 | 95.3% |
