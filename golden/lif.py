"""Leaky integrate-and-fire (LIF) neuron -- floating-point reference.

This is the seed of the golden model. It deliberately does NOT use PyTorch or
snnTorch: it is a plain loop over timesteps that we control line by line, so
that when hardware disagrees with it we can point at exactly which line.

The recurrence, per timestep n:

    V[n] = beta * V[n-1] + I[n] - (reset applied here or one step later)
    s[n] = 1 if V[n] crosses threshold else 0

Two details below look pedantic and are not. They are the two places where a
"correct-looking" implementation silently stops being bit-identical to another
one, and we will pay for them in M2 if we get them wrong now.
"""

from typing import Tuple

import numpy as np


def lif_step(
    current: np.ndarray,
    beta: float,
    threshold: float,
    reset_delay: bool = True,
    fire_on_equal: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Run one LIF neuron over a 1-D sequence of input currents.

    :param current: input current I[n], shape (T,). One value per timestep.
    :param beta: membrane decay. V keeps this fraction of itself each step.
        beta=1.0 is a perfect integrator (no leak); beta=0.0 forgets instantly.
    :param threshold: V must cross this to emit a spike.
    :param reset_delay: WHEN the threshold subtraction is applied.
        True  -- subtract on the step AFTER the crossing (snnTorch's default).
        False -- subtract on the same step as the crossing (the model written
                 in the project brief, and the one that is natural in hardware).
    :param fire_on_equal: whether V exactly equal to threshold counts as a
        spike. False means "V > threshold" (snnTorch). True means
        "V >= threshold" (as written in the project brief). With floats this almost
        never matters; with the integers we move to in M1 it matters a lot,
        because exact equality is common.
    :return: (spikes, membrane) each of shape (T,). spikes is 0.0/1.0.
    """
    current = np.asarray(current)
    # Arithmetic happens in the input's dtype. Pass a float32 array and every
    # multiply-add below rounds exactly the way PyTorch's float32 does, which
    # is what lets the demo assert equality rather than "closeness".
    dt = current.dtype
    n_steps = current.shape[0]

    beta = dt.type(beta)
    threshold = dt.type(threshold)

    spikes = np.zeros(n_steps, dtype=dt)
    membrane = np.zeros(n_steps, dtype=dt)

    v = dt.type(0)  # V[-1]: the neuron starts at rest
    for n in range(n_steps):
        # Was the PREVIOUS membrane above threshold? Only used by reset_delay.
        fired_before = _crossed(v, threshold, fire_on_equal)

        v = beta * v + current[n]
        if reset_delay and fired_before:
            v = v - threshold

        fired = _crossed(v, threshold, fire_on_equal)
        if fired and not reset_delay:
            v = v - threshold

        spikes[n] = 1 if fired else 0
        membrane[n] = v

    return spikes, membrane


def _crossed(v: float, threshold: float, fire_on_equal: bool) -> bool:
    return v >= threshold if fire_on_equal else v > threshold
