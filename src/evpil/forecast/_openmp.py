"""Import-order guard for the two libraries that each ship their own OpenMP.

On macOS, XGBoost and PyTorch load separate OpenMP runtimes into one process.
The result is not a warning and not a slowdown:

    import torch            # then, later
    xgb.XGBRegressor().fit(X, y)      -> SIGSEGV, inside xgboost's own data path

and in the other direction, an LSTM forward pass large enough to take the
parallel path hangs instead. Both were reached by ordinary use here: the ladder
fits XGBoost and then trains an LSTM, and the test suite imports torch in one
module and fits XGBoost in another.

Two things fix it and one does not:

  - **Importing xgboost before torch works**, and costs nothing. Both libraries
    keep all their threads.
  - Setting `OMP_NUM_THREADS=1` before either import works, and costs XGBoost
    roughly a factor of eight. Not used.
  - `torch.set_num_threads(1)` after the fact does *not* fix the segfault
    direction. It fixes only the hang, which is why `fit_lstm` also does it.

So the rule is an ordering one, and ordering can only be established before
torch is first imported. Call `ensure_import_order()` from anywhere that is
about to import torch, and from `conftest.py` so it applies to a whole test
session.
"""

from __future__ import annotations

import sys
import warnings


def ensure_import_order() -> bool:
    """Import xgboost first, if it is installed and torch is not yet loaded.

    Returns True when the order is guaranteed. Returns False, with a warning,
    when torch was already imported by someone else: nothing can repair that
    from here, and a warning beats a segfault with no explanation attached.
    """
    if "torch" in sys.modules:
        if "xgboost" not in sys.modules:
            warnings.warn(
                "torch was imported before xgboost. On macOS these load two "
                "OpenMP runtimes and a later xgboost fit segfaults. Call "
                "evpil.forecast._openmp.ensure_import_order() before importing "
                "torch -- see that module for the detail.",
                RuntimeWarning,
                stacklevel=2,
            )
        return False

    try:
        import xgboost  # noqa: F401
    except ImportError:
        # Only torch is installed, so there is no conflict to order.
        pass
    return True
