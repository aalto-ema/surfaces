# Contributing

Small, focused changes are easiest to review. Read [AGENTS.md](AGENTS.md) and the
[product](docs/PRODUCT.md), [architecture](docs/ARCHITECTURE.md), and
[design](docs/DESIGN.md) notes before changing core workflows.

## Set up

Use Python 3.11 or newer in a virtual environment:

```sh
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux, or
`.venv\Scripts\Activate.ps1` in Windows PowerShell, then run:

```sh
python -m pip install -e ".[dev]"
python run_app.py
```

## Check a change

```sh
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

For headless Qt tests, set `QT_QPA_PLATFORM=offscreen` and `PYTEST_QT_API=pyside6`.
On macOS/Linux, prefix the test command with those environment assignments; in
PowerShell, set `$env:QT_QPA_PLATFORM = "offscreen"` before running tests.

Use meaningful behavioral tests for scientific results, seeded compositions,
project round trips, and export semantics. Inspect the actual UI and exported
figures when changing rendering; tests cannot establish aesthetic quality alone.

New compound prototypes need a documented basis/cell convention, a scientific
reference, bulk/slab stoichiometry checks, and appropriate site/coordination tests.
Update the runtime catalog and [compound guide](docs/COMPOUNDS.md) together.

## Documentation and screenshots

README images show the real app with the public example projects. Regenerate them
from the repository root after relevant UI changes:

```sh
python tools/capture_screenshots.py
```

The capture script renders only the app window in offscreen mode, so no desktop,
private browser, or unrelated document content enters the images. Review both PNGs
before committing them. Keep paths relative so images work on GitHub and in a clone.

## Issues and pull requests

Report reproducible bugs with platform/version details and a minimal construction
recipe. Remove private paths and confidential structures from logs and attachments.
For a pull request, describe the final behavior and its validation; include a
screenshot when the UI changes. Keep geometry edits independent of display styling,
and explain approximations or scientific assumptions explicitly.
