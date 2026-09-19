# IsaacGym port of the year-two student (2026-09-18)

What this is: the AMD-box recreation's three pieces -- the frame-difference
event simulator, the 58k FPGA-sized spiking encoder, and distillation --
moved onto ES-Parkour's real stack (extreme-parkour + IsaacGym) on the
NVIDIA box, without modifying extreme-parkour.

| piece | recreation | here |
|---|---|---|
| event simulator | `es_parkour/event_sim.py`, numpy, one env at a time | `event_sim_torch.py`, batched on the GPU; bit-identical (test_port.py) |
| encoder | `es_parkour/fpga_encoder.py` | `fpga_encoder.py`, verbatim (test_port.py diffs them) |
| where it plugs in | custom Distiller + GRU + spiking actor | extreme-parkour's own `learn_vision` DAgger loop: we replace `depth_encoder.base_backbone` only (`fpga_event_backbone.py`); their GRU, student actor, checkpoints and logs stay |
| launcher | `scripts/distill_fpga.py` | `train_fpga_student.py` (mirrors their train.py, then swaps the backbone and recreates the optimisers) |

Checks: `python3 robot/isaac/test_port.py` (CPU, no IsaacGym): PASS on
2026-09-18. **End-to-end smoke on the box: PASSED 2026-09-18 23:48** (8
camera envs, 2 iterations of their learn_vision with the FPGA backbone
in place: 4.5-4.7 s per iteration, depth-actor loss 4.59, yaw loss 2.03,
event-bit rate 0.094 at the last tick). The first attempt beside the
teacher failed at PhysX sim creation (CUDA out-of-memory, 3 GB free);
the second, on the free GPU, failed at their wandb.log() because the
launcher had not called wandb.init() as their train.py does (fixed);
the third passed.

## Recorder and vector export (2026-09-18, window = repeat)

`record_event_frames.py` runs inside extreme-parkour with the camera envs,
drives them with the teacher (or `--student <exptid>` once one exists),
converts every camera tick to an event frame with the backbone's own
simulator/mapping/binarisation, and saves one tick frame per sample,
round-robin over environments after a warm-up, with `window="repeat"`
in the file. `sim/export_fpga_student_vectors.py --name i1` repeats each
frame over T = 4 (the student's direct coding), quantises the encoder's
conv1 from either checkpoint layout (recreation `fpga_student.pt` or the
rsl_rl runner's `depth_encoder_state_dict`), writes the `i1` vector set
plus `i1_thresh.txt`, and the bench runners (`run_ed_tb.sh i1`,
`run_conv_p_tb.sh i1`, env `I1_FRAMES` / `I1_CKPT`) read the threshold
from that file. The export path was proven end to end on a fake recorder
file with corner activity (ED K=4 and dense P=4 bit-identical) before any
real frames existed; real frames arrived 2026-09-18 23:48: 64 teacher-driven tick frames
(`robot/artifacts/isaac_event_frames.npz`), mean event-bit rate 5.7 %,
per-frame 0.9-19.5 %. Exported as `i1` with the recreation's student
weights (threshold 16): corner exposure TL 0 / TR 0 / BL 24 / BR 20 of
32 -- the top corners are blind here as they were on the MuJoCo frames
(the camera's top rows see beyond the 2 m clip, so nothing changes
there), which is why the synthetic r1 set stays the ladder's guard.
Both engines bit-identical on the real frames (ED K=4: 1,048,576
comparisons, 19,372 input spikes; dense P=4: 1,572,864 comparisons).
ED K=4 per sample: mean 185,616 cycles (1.86 ms), min 147,472, max
251,872 (spread 1.71x) against dense P=4 at 360,444 cycles (3.60 ms):
ED 1.94x on the mean, 1.43x on the worst frame. These are the year-two
workload's C1 numbers with placeholder (MuJoCo-distilled) weights; the
cycles are weight-independent for a given frame set, the accuracy is not.

## Distillation cost, measured (2026-09-18 23:53)

Stock 192 camera envs, 3 iterations: **13.6-14.0 s per iteration**
(losses 4.59 -> 3.39 actor, 2.03 -> 1.47 yaw over three iterations).
5k iterations = 19 h, 10k = 39 h on the 1080 Ti; the GPU is otherwise
idle now that the teacher has finished.

## Evaluation wrapper (2026-09-18)

`evaluate_parkour.py` reports the paper's Fig. 5 quantity -- success rate
per parkour terrain (gap, step, hurdle, parkour) -- for `--policy teacher`
(scandots, no camera), `student` (their stock depth student) or `fpga`
(ours, `--fpga_run <exptid>`), under ONE protocol copied from their
evaluate.py: 256 envs, 20 s episodes, the four terrains at equal share,
random difficulty (`--max_difficulty` for the hardest rows), noise,
friction randomisation and pushes on, no curriculum. Success = the
episode ended by reaching all 8 waypoints; their code folds that into
`time_outs`, and `eval_tally.py` separates it from a real time-out by the
pre-step episode length (a time-out fires on the step after the limit).
It also reports fall rate, time-out rate, waypoints reached / 8 (their
"mean number of waypoints") and mean episode length, per terrain, as a
markdown table plus a JSON file (`--out`). The tally is unit-tested in
test_port.py; the IsaacGym part runs on the box after the GPU is free.
The paper's numbers (Fig. 5: gap 45 %, step 60 %, hurdle 71 %, parkour
29 %) are for its own protocol, which the paper does not fully specify;
the like-for-like comparison is teacher vs stock student vs FPGA student
under THIS protocol on THIS box.

## GIF recorder (2026-09-19)

`record_gifs.py` writes one GIF per parkour terrain of the robot
COMPLETING the course: a follow camera per environment (headless
camera sensors, read back each control step), episodes that fall or
time out discarded, the first successful episode per terrain saved at
25 fps (`<policy>_<terrain>.gif`). Same three policies as the evaluator.
Status: compiles; its IsaacGym run is queued behind the distillation
(a second PhysX simulation cannot be created beside the 9 GB the
distillation holds -- the same failure the first smoke had).

## Distillation run (launched 2026-09-19 13:10)

`200-00-fpga`: 10,000 iterations, 192 camera envs, repeat window,
binarised frames, resumed from the teacher; 13.5 s per iteration, ETA
~37.5 h. `~/post_distill.sh` on the box waits for it and then records
teacher and student GIFs, evaluates the student under the shared
protocol, and records student-driven event frames.

## Choices made in the port (judgement calls, flagged)

- **Window.** The recreation's student repeats ONE event frame over the
  T=4 spiking timesteps (direct coding), but its vector recorder exported
  four CONSECUTIVE tick frames, so the r1 hardware vectors were not what
  that student saw. `--window repeat` (default, paper-faithful) or
  `--window consecutive`; whichever is used for training must be used for
  the vector export.
- **Binarised frames.** The hardware receives 1-bit events (D0003); the
  recreation trained on counts/8 and exported binarised. Default here is
  binarised in training (`--counts` restores the recreation's behaviour).
- **Depth range.** extreme-parkour clips depth at 2 m (the recreation's
  camera used 4 m); intensity = 1 - d/2. Their normalised image maps to
  it by `0.5 - x`. The image is their crop of the 106x60 render, resized
  to 64x64 (a mild horizontal squash; the recreation rendered square).
- **Yaw head.** Their GRU path produces the yaw the loop supervises; the
  encoder's own +2 outputs (kept so the FC is 1024 -> 34 as in P1 / r1)
  are unsupervised here.
- **Episode starts** re-seed the event reference and zero the history;
  their GRU state is not reset on episode boundaries (stock), left alone.

## Cost

Their distillation runs 192 camera envs x 120 steps per iteration. On the
1080 Ti the teacher ran ~6x slower than a 3090; expect the same ratio.
Do not start it while the teacher is training (GPU memory).
