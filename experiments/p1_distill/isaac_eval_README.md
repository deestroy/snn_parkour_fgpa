# Year-two evaluations on the real stack (extreme-parkour + IsaacGym, 1080 Ti)

Protocol: `robot/isaac/evaluate_parkour.py` = their evaluate.py's settings
(256 envs, 20 s episodes, the four parkour terrains at equal share, random
difficulty, noise + friction randomisation + pushes on, no curriculum),
1,500 control steps. Success = all 8 waypoints reached before the time
limit. One protocol for every row so the rows compare.

## Teacher (scandots, no camera), run 100-00-teacher, checkpoint model_14500 (2026-09-18 23:49)

| terrain | episodes | success | fall | time-out | waypoints reached | mean length (steps) |
|---|---|---|---|---|---|---|
| gap | 107 | 95.3 % | 4.7 % | 0.0 % | 0.98 | 564 |
| hurdle | 76 | 96.1 % | 1.3 % | 2.6 % | 0.99 | 762 |
| parkour | 316 | 97.2 % | 2.8 % | 0.0 % | 0.99 | 423 |
| step | 122 | 99.2 % | 0.8 % | 0.0 % | 0.99 | 510 |

JSON: `isaac_eval_teacher_20260918.json`. The paper's Fig. 5 numbers
(gap 45 %, step 60 %, hurdle 71 %, parkour 29 %) are its STUDENT's,
under its own, not fully specified, protocol; they are context, not a
comparison. The rows that compare are the ones below, when they exist.

## Students

| student | gap | step | hurdle | parkour | notes |
|---|---|---|---|---|---|
| their stock depth student | -- | -- | -- | -- | not yet trained on this box |
| FPGA event student (58k, repeat window) | -- | -- | -- | -- | not yet trained; smoke passed 2026-09-18 |
