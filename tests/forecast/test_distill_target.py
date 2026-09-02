"""The identity `scripts/run_distill.py` relies on instead of a distillation loss.

The script trains its distilled students with the ordinary trainer, handing it
a blended target rather than a blended loss function. That is only legitimate
because, for a squared-error objective,

    a*||s - y||^2 + b*||s - t||^2  =  ||s - (a*y + b*t)||^2 + c(y, t),   a + b = 1

where the leftover term does not involve the student's output `s`, so the two
have identical gradients and identical minimisers. If that were false the
distilled arms would be optimising something other than what the write-up says
they optimise, and the ablation would be measuring the wrong thing.

It is an algebraic identity rather than an empirical claim, which is exactly
why it is cheap to pin and expensive to get wrong unnoticed.
"""

from __future__ import annotations

import numpy as np
import pytest


def blended_loss(s, y, t, a):
    return a * ((s - y) ** 2).mean() + (1 - a) * ((s - t) ** 2).mean()


def target_loss(s, y, t, a):
    return ((s - (a * y + (1 - a) * t)) ** 2).mean()


@pytest.mark.parametrize("alpha", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_difference_between_the_two_losses_does_not_depend_on_the_student(alpha):
    rng = np.random.default_rng(0)
    y = rng.normal(size=(64, 30)) * 1000.0
    t = y + rng.normal(size=(64, 30)) * 250.0

    gaps = []
    for _ in range(6):
        s = rng.normal(size=(64, 30)) * 1000.0
        gaps.append(blended_loss(s, y, t, alpha) - target_loss(s, y, t, alpha))

    # Every student gives the same gap, so the gap is a constant in s and the
    # two objectives differ by something with no gradient.
    assert np.allclose(gaps, gaps[0], rtol=0, atol=1e-8)


@pytest.mark.parametrize("alpha", [0.0, 0.3, 0.5, 1.0])
def test_the_two_losses_have_the_same_gradient_in_the_student(alpha):
    rng = np.random.default_rng(1)
    y = rng.normal(size=(32, 30)) * 1000.0
    t = y + rng.normal(size=(32, 30)) * 400.0
    s = rng.normal(size=(32, 30)) * 1000.0

    n = s.size
    grad_blended = (2.0 / n) * (alpha * (s - y) + (1 - alpha) * (s - t))
    grad_target = (2.0 / n) * (s - (alpha * y + (1 - alpha) * t))
    assert np.allclose(grad_blended, grad_target, rtol=1e-12, atol=1e-12)


def test_alpha_one_is_ordinary_training_and_alpha_zero_is_pure_distillation():
    rng = np.random.default_rng(2)
    y = rng.normal(size=(16, 30))
    t = rng.normal(size=(16, 30))
    assert np.allclose(1.0 * y + 0.0 * t, y)
    assert np.allclose(0.0 * y + 1.0 * t, t)
