# Control-loop fundamentals briefing (written for the physical-robot plan;
# kept after the 2026-08-20 simulation pivot — the concepts transfer, the
# hazards become experiment-integrity risks instead of physical ones)

Written 2026-08-19 for the year-two start, per the year-two plan's
explain-first list. Read before any robot session. Platform-agnostic —
nothing here depends on Go1 vs Go2 (unresolved; blocks all SDK code).

## The control loop and the control period

A legged robot is controlled by a loop that runs at a FIXED rate: read
sensors, compute, command motors, wait for the next tick. The time between
ticks is the control period. Ours (from the parkour literature the policy
comes from): the POLICY runs at 50 Hz (period 20 ms), and an onboard PD
controller runs at ~1 kHz turning the policy's targets into motor torques.
"Real-time" does not mean "fast"; it means "the deadline is part of
correctness" — a result at 21 ms is not a slower answer, it is a WRONG one,
because the physical world moved on without it.

## Deadline, and what a miss does physically

While the robot walks, it is perpetually falling and catching itself. The
policy's job each tick is to place the catch. Miss one tick and the last
command is a tick stale — usually survivable (the 1 kHz PD keeps tracking
the old target). Miss several in a row while the body is mid-flight over an
obstacle and the catch never arrives: the robot lands wrong and falls at
speed. This is why the thesis treats deadline-miss RATE as a first-class
measured quantity, and why a late accelerator is a broken accelerator no
matter how energy-efficient (the whole year-one argument, embodied).

## High-level vs low-level control

High-level: "walk forward at 0.5 m/s" — the factory controller's interface;
the robot's own software does everything. Low-level: "joint 7, be at 0.43
rad" — 12 joint targets per tick, nothing between you and the motors except
the PD loop and the safety limits. The learned policy NEEDS low-level (it
was trained to emit joint positions). R0 uses high-level (factory app) only
to prove the robot works; everything after R1 is low-level.

## PD control, and what Kp and Kd physically are

The onboard controller computes torque = Kp*(target - position) +
Kd*(0 - velocity). Kp is a SPRING pulling the joint to the target: too low
and the leg is mushy and never reaches it; too high and it snaps there,
overshoots, oscillates, and hits like a hammer. Kd is a DAMPER resisting
motion: it eats oscillation; too high and the joint is sluggish and hot.
We START from the literature's values (Kp=50, Kd=1 for A1-class hardware,
confirm for ours) and change nothing until R2 walks — tuning gains blind on
a 12 kg machine is how hardware gets destroyed.

## Torque vs position vs velocity control; why the policy emits positions

Motors can be commanded in torque (force), velocity, or position. The
policy emits POSITIONS because they are bounded and interpretable — a bad
position command is a wrong pose; a bad torque command is a wrong
ACCELERATION, which through 20 ms of integration is a launch. The torque
ceiling (~25 Nm, confirm) is enforced BELOW the policy: a clip the network
cannot argue with.

## Damping mode and the safe state

Damping mode: motors resist motion like shock absorbers — they hold
nothing, they just dissipate. The robot sags to the floor. This is the safe
state because it requires no correct information: holding the last pose is
wrong if the last pose was mid-stride; going limp drops the robot 30 cm
gently. Every failure path ends in damping mode, and the operator must be
able to trigger it from the remote WITHOUT LOOKING.

## Watchdogs and failing safe

A watchdog is a timer the healthy loop keeps resetting; if the loop stalls,
the timer fires and forces the safe state. Ours has a twist (the plan's
"watchdog paradox"): deadline misses are our PRIMARY DATA as well as the
hazard, so the watchdog must LOG every miss (which stage, by how much),
TOLERATE isolated misses (hold last command one cycle, log it), and
ESCALATE to damping only after N consecutive misses (N configured and
logged). A watchdog that hides misses destroys the experiment; none at all
destroys the robot.

## Joint state, IMU, odometry — what each sensor really tells you

Joint encoders: position/velocity per joint — accurate, trust them. IMU:
orientation and angular velocity of the body — good short-term, drifts in
yaw, trust pitch/roll. Odometry (position in the world, integrated from
legs+IMU): drifts continuously — never trust it for anything that matters
over more than a few strides. The policy uses joints + IMU + depth camera;
it does not need world position.

## Sim-to-real gap

The policy was trained in simulation: perfect depth, ideal motors, one
friction model. Reality: the D435 returns holes and flying pixels on dark/
shiny surfaces; motors have backlash and heat; floors vary. Standard
mitigations (the literature's): depth preprocessing (clip, fill holes,
smooth — same pipeline as training), domain randomisation already baked
into training, and R4's rule: run the FPGA path ALONGSIDE the working
controller and compare outputs before it ever commands anything.

## Jitter vs latency

Latency = how late on average; jitter = how variable. A loop that is
always 15 ms late is usable (compensate once); one that is 5 ms +/- 15 is
poison — the PD sees commands arriving at random phases. R1's deliverable
is a HISTOGRAM of loop periods, not a mean.

## UDP vs DDS (why Go1-vs-Go2 gates everything)

Go1: unitree_legged_sdk, raw UDP packets on the robot's internal
192.168.123.x network — you send a packed struct, nothing guarantees
delivery or ordering, and the code is C++ against a fixed header. Go2:
unitree_sdk2 on DDS (CycloneDDS) — a publish/subscribe middleware with
discovery and QoS. Different APIs, wire formats, network models. Nothing
interface-shaped can be written until the robot model is confirmed.
