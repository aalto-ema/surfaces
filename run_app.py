"""Launch the local source checkout from any working directory."""

import importlib.util
import os
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    missing = [
        name
        for name in ("ase", "PySide6", "numpy", "PIL")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        environment = root / ".venv"
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if python.exists() and Path(sys.prefix) != environment:
            os.execv(str(python), [str(python), str(root / "run_app.py"), *sys.argv[1:]])
        print("Missing dependencies: " + ", ".join(missing), file=sys.stderr)
        print("Install with: python -m pip install -e '.[dev]'", file=sys.stderr)
        return 1
    sys.path.insert(0, str(root / "src"))
    from surfaces.app import main as start_app

    return start_app()


if __name__ == "__main__":
    raise SystemExit(main())
