# ES-Parkour recreation - evaluation results

Level 3, 8 episodes/terrain.

## Success rates (cf. paper Fig. 5)

| Terrain | Teacher ANN | Student SNN |
|---|---|---|
| gap | 100% | 0% |
| step | 100% | 12% |
| hurdle | 100% | 0% |
| parkour | 38% | 0% |

## Joint motor energy per episode (cf. Table IV)

| Terrain | Teacher (J) | Student (J) |
|---|---|---|
| gap | 8238.5 | 1444.9 |
| step | 8993.4 | 6793.5 |
| hurdle | 8643.4 | 5849.4 |
| parkour | 6146.4 | 5070.1 |

## Operations & theoretical energy (cf. Tables II-III)

| Module | SNN FLOPs | SNN SOPs | ANN FLOPs | OPs(SNN):OPs(ANN) | SNN mJ | ANN mJ | Saving |
|---|---|---|---|---|---|---|---|
| encoder (0.06M) | 1.18e+06 | 5.33e+05 | 1.45e+08 | 0.01 : 1 | 0.005906 | 0.6663 | 99.1% |
| actor (0.23M) | 0 | 5.74e+04 | 2.32e+05 | 0.25 : 1 | 5.17e-05 | 0.001067 | 95.2% |
