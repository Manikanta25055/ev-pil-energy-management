"""The exact Wilcoxon signed-rank test used for the B2 verdict.

Hand-enumerated cases for both sign directions, tied magnitudes and zeros,
so the verdict does not rest on an implementation checked only on one side.
"""

import pytest

from scripts.b2_repeats_stats import average_ranks, wilcoxon_exact


def test_average_ranks_share_tied_positions():
    assert average_ranks([3.0, 1.0, 1.0, 2.0]) == [4.0, 1.5, 1.5, 3.0]


def test_all_positive_twelve_gives_two_extreme_assignments():
    w = wilcoxon_exact([float(i) for i in range(1, 13)])
    assert w["T"] == 0.0 and w["w_plus"] == 78.0
    assert w["p_two_sided"] == pytest.approx(2 / 4096)


def test_sign_direction_does_not_change_p():
    up = [0.5, 1.2, -0.1, 2.0, 0.3, 0.9, 1.1, 0.7]
    down = [-x for x in up]
    assert wilcoxon_exact(up)["p_two_sided"] == wilcoxon_exact(down)["p_two_sided"]
    assert wilcoxon_exact(up)["w_plus"] == wilcoxon_exact(down)["w_minus"]


def test_one_smallest_negative():
    # Ranks 1..12, rank 1 negative: T = 1, assignments with min(W+, W-) <= 1
    # are W+ in {0, 1} and W- in {0, 1}: 4 of 4096.
    d = [-1.0] + [float(i) for i in range(2, 13)]
    w = wilcoxon_exact(d)
    assert w["T"] == 1.0
    assert w["p_two_sided"] == pytest.approx(4 / 4096)


def test_ties_use_average_ranks():
    # |d| all equal: ranks 2, 2, 2; W+ = 4, W- = 2, T = 2; every assignment
    # has min(W+, W-) <= 2, so p = 1.
    w = wilcoxon_exact([1.0, 1.0, -1.0])
    assert (w["w_plus"], w["w_minus"], w["T"]) == (4.0, 2.0, 2.0)
    assert w["p_two_sided"] == 1.0


def test_zeros_are_dropped():
    w = wilcoxon_exact([0.0, 0.0, 1.0, 2.0])
    assert w["n_nonzero"] == 2
    assert w["p_two_sided"] == pytest.approx(0.5)


def test_all_zero_gives_one():
    w = wilcoxon_exact([0.0, 0.0, 0.0])
    assert w["n_nonzero"] == 0 and w["p_two_sided"] == 1.0
