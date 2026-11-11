"""Keep license files and exact Qt/Python source references with the installer."""

import shutil
import sys
from importlib import metadata
from pathlib import Path

from PySide6.QtCore import qVersion


def collect(bundle: Path) -> None:
    directory = bundle / "licenses"
    directory.mkdir()
    shutil.copy2("LICENSE", directory / "Surfaces.txt")
    for candidate in ("LICENSE.txt", "LICENSE"):
        python_license = Path(sys.base_prefix) / candidate
        if python_license.is_file():
            shutil.copy2(python_license, directory / "Python.txt")
            break
    else:
        raise FileNotFoundError("Could not find the bundled Python runtime's license.")

    entries = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        entries.append(f"{name} {dist.version}")
        for file in dist.files or ():
            is_notice = file.name.lower().startswith(("license", "copying", "notice", "copyright"))
            is_notice |= "licenses" in {part.lower() for part in file.parts}
            if is_notice and not file.is_absolute() and ".." not in file.parts:
                if not dist.locate_file(file).is_file():
                    continue
                target = directory / name / file
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dist.locate_file(file), target)

    qt = qVersion()
    series = qt.rsplit(".", 1)[0]
    pyside = metadata.version("PySide6")
    python = ".".join(map(str, sys.version_info[:3]))
    (bundle / "THIRD-PARTY-NOTICES.txt").write_text(
        "Surfaces is MIT-licensed. See the licenses folder for component notices.\n"
        "Qt is used through the open-source Qt for Python distribution.\n"
        "Qt DLLs and plugins are installed as separate, replaceable files. You may\n"
        "replace them with ABI-compatible builds and debug your modifications.\n"
        "The PySide6 modules are installed outside the executable archive.\n\n"
        f"Qt {qt} corresponding source (upstream):\n"
        f"https://download.qt.io/archive/qt/{series}/{qt}/single/\n"
        f"PySide6 and Shiboken {pyside} corresponding source (upstream):\n"
        f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{pyside}-src/\n"
        f"Python {python} source: https://www.python.org/ftp/python/{python}/\n"
        "Surfaces source: https://github.com/aalto-ema/surfaces\n\n"
        "Build environment packages (includes build tools):\n"
        + "\n".join(sorted(entries, key=str.casefold))
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    collect(Path(sys.argv[1]))
