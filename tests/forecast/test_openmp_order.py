"""The import-order guard, proved in a fresh interpreter.

This has to run in a subprocess. The fault it defends against is a segfault
that kills the whole process, and the ordering it fixes can only be established
before torch is first imported -- both of which make an in-process test either
impossible or meaningless, since this session already has the order right.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("torch")
pytest.importorskip("xgboost")

FIT = textwrap.dedent(
    """
    import numpy as np, xgboost as xgb
    rng = np.random.default_rng(0)
    A = rng.normal(size=(400, 24)).astype(np.float32)
    xgb.XGBRegressor(n_estimators=20, tree_method="hist",
                     n_jobs=1).fit(A, A[:, 0].astype(np.float64), verbose=False)
    print("ok")
    """
)


def _run(source: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", source], capture_output=True,
                          text=True, timeout=300)


def test_the_guard_makes_torch_first_safe():
    guarded = _run(
        "import sys; sys.path.insert(0, 'src')\n"
        "from evpil.forecast._openmp import ensure_import_order\n"
        "assert ensure_import_order() is True\n"
        "import torch\n" + FIT
    )
    assert guarded.returncode == 0, guarded.stderr[-2000:]
    assert "ok" in guarded.stdout


def test_the_fault_the_guard_exists_for_is_real():
    # Without the guard the same program dies on a signal. If this ever starts
    # passing, the platform has been fixed and the guard can be reconsidered --
    # so the test is written to notice that too, rather than only to fail.
    unguarded = _run("import torch\n" + FIT)
    if unguarded.returncode == 0:
        pytest.skip(
            "torch before xgboost no longer crashes on this machine; "
            "the guard in evpil.forecast._openmp may no longer be needed"
        )
    assert unguarded.returncode < 0 or unguarded.returncode > 128, (
        f"expected a signal, got exit {unguarded.returncode}"
    )


def test_the_guard_warns_when_it_is_already_too_late():
    late = _run(
        "import sys, warnings; sys.path.insert(0, 'src')\n"
        "import torch\n"
        "from evpil.forecast._openmp import ensure_import_order\n"
        "with warnings.catch_warnings(record=True) as w:\n"
        "    warnings.simplefilter('always')\n"
        "    assert ensure_import_order() is False\n"
        "assert any(issubclass(x.category, RuntimeWarning) for x in w), w\n"
        "print('warned')\n"
    )
    assert late.returncode == 0, late.stderr[-2000:]
    assert "warned" in late.stdout
