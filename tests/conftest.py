"""Session-wide setup that has to happen before any test module is imported.

`tests/forecast/test_deploy.py` imports torch to cross-check a parameter count,
and `tests/forecast/test_models.py` fits XGBoost. Alphabetically the first runs
first, which put the process in the ordering that segfaults. Establishing the
order here fixes it for every module regardless of collection order, and costs
nothing at run time.
"""

from evpil.forecast._openmp import ensure_import_order

ensure_import_order()
