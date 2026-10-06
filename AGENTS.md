# Repository Guidelines

## Project Structure & Module Organization

`src/evpil/` contains the Python package: `plant/` models vehicle dynamics, `control/` implements controllers, `forecast/` contains prediction models, and `data/` handles datasets and splits. `firmware/main/` contains ESP-IDF C code; `firmware/host_test/` provides native C harnesses. `scripts/` holds simulation, training, deployment, plotting, and report commands. Tests live in `tests/`, with domain subdirectories. Experiment records and figures live in `docs/`; generated reports live in `reports/`.

## Build, Test, and Development Commands

Run commands from the repository root using Python 3.11 or newer:

- `python3 -m venv .venv` and `source .venv/bin/activate`: create and activate an isolated environment.
- `python3 -m pip install -e '.[dev]'`: install the package and pytest tools. Add `rl` or `geo` extras only when needed.
- `pytest tests -q`: run the Python suite, including native C parity checks.
- `make -C firmware/host_test check`: build and run protocol/control harnesses with a C compiler.
- `./scripts/idf.sh build`: build firmware; set `IDF_PATH` to your ESP-IDF checkout.
- `python3 -m scripts.run_control_baselines --help`: inspect local simulation options; use `--cycles udds` for a training-cycle run and explicit output paths for new experiments.

## Coding Style & Naming Conventions

Use four-space indentation in Python and C, following adjacent code. Use `snake_case` for functions, modules, and variables; `PascalCase` for Python classes; and uppercase constants. Include units in physical quantities, such as `p_limit_w` and `v_mps`. Add Python type hints to interfaces. No formatter or linter is configured; native C harnesses enforce C11 with `-Wall -Wextra -Werror`.

## Testing Guidelines

Use pytest files named `test_*.py` and descriptive `test_*` functions. Add regression tests for behavior changes, especially physical bounds, protocol layout, action decoding, and Python/C parity. Run focused tests during development, then the full suite before submitting. No numeric coverage threshold is configured.

## Commit & Pull Request Guidelines

History uses descriptive, sentence-style subjects explaining the change or correction. Keep commits focused. PR descriptions should state the problem, resulting behavior, validation commands, and hardware/data prerequisites. Link relevant issues and experiment records; include figures when plots change.

## Data & Experiment Integrity

Keep raw datasets and trained checkpoints out of Git as specified in `.gitignore`. Preserve declared training, validation, and sealed test splits. Record seeds, parameters, firmware versions, and output paths; keep campaigns using different firmware separate.
