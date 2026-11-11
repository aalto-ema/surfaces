"""Entry point for the Windows executable and its noninteractive install check."""

import sys
import traceback
from pathlib import Path

from surfaces.app import configure_app, main
from surfaces.window import MainWindow


def check_installation(report: Path) -> int:
    """Exercise the installed Qt, ASE, SciPy, scikit-image and Pillow runtime."""
    try:
        from ase.io import write
        from PIL import Image
        from PySide6.QtWidgets import QApplication

        from surfaces.compounds import EXAMPLES
        from surfaces.exporting import export_figure
        from surfaces.model import ExportSettings, ParticleSpec, StructureSpec
        from surfaces.structures import build_project, import_project

        app = QApplication([sys.argv[0]])
        configure_app(app)
        window = MainWindow()
        window.show()
        app.processEvents()
        viewport = window.viewport.grab()
        if viewport.isNull() or not window.viewport.projected:
            raise RuntimeError("The default slab did not render in the installed Qt window.")

        atoms = window.project.atoms
        for name in ("test.cif", "test.xyz", "test.extxyz", "test.traj", "test.vasp"):
            path = report.parent / name
            write(path, atoms)
            if len(import_project(str(path)).atoms) != len(atoms):
                raise RuntimeError(f"ASE import failed for {name}.")

        if not len(build_project(EXAMPLES[0].spec()).atoms):
            raise RuntimeError("The packaged compound builder did not generate a structure.")

        project = build_project(
            StructureSpec(particle=ParticleSpec(shape="chiral_rod", mesh_resolution=32))
        )
        if project.mesh is None or not len(project.atoms):
            raise RuntimeError("The packaged morphology builder did not generate its mesh.")
        path = report.with_suffix(".png")
        export_figure(project, ExportSettings(width=320, height=240, transparent=True), path)
        with Image.open(path) as image:
            if image.size != (320, 240) or image.getchannel("A").getextrema() != (0, 255):
                raise RuntimeError("The installed app did not export the expected transparent PNG.")

        window.close()
        app.processEvents()
        report.write_text("OK\n", encoding="utf-8")
        return 0
    except Exception:
        report.write_text(traceback.format_exc(), encoding="utf-8")
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--installer-smoke-test":
        raise SystemExit(check_installation(Path(sys.argv[2])))
    raise SystemExit(main())
