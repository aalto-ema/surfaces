"""Desktop workspace: scientific state, controls, and asynchronous operations."""

import copy
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from surfaces.appearance_ui import AppearancePanel
from surfaces.composition_ui import CompositionPanel
from surfaces.compound_ui import CompoundExamplesDialog
from surfaces.compounds import C_AXIS_PROTOTYPES, EXAMPLES, PROTOTYPES, U_PROTOTYPES, parse_formula
from surfaces.export_ui import ExportDialog
from surfaces.model import StructureSpec
from surfaces.persistence import load_project, save_project
from surfaces.rendering import Viewport
from surfaces.structures import (
    build_project,
    import_project,
    layer_indices,
    reference_lattice,
    validate_spec,
)
from surfaces.ui_common import Tasks, decimal, heading, integer, panel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = build_project(StructureSpec())
        self.undo_stack = []
        self.redo_stack = []
        self.dirty = False
        self.path = None
        self.form_spec = None
        self.busy = False
        self.callback = None
        self.after_idle = None
        self.completed_message = None
        self.tasks = Tasks(self)
        self.tasks.result.connect(self.task_result)
        self.tasks.error.connect(self.show_error)
        self.tasks.idle.connect(self.task_idle)
        self.setWindowTitle("Surfaces")
        self.resize(1360, 900)
        self.setMinimumSize(960, 680)
        self.toolbar = QToolBar("Project")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self.action("Open", self.open_project, QKeySequence.StandardKey.Open)
        self.action("Save", self.save, QKeySequence.StandardKey.Save)
        self.action("Save as…", lambda: self.save(save_as=True), QKeySequence.StandardKey.SaveAs)
        self.action("Import structure…", self.import_structure)
        self.toolbar.addSeparator()
        self.undo_action = self.action("Undo", self.undo, QKeySequence.StandardKey.Undo)
        self.redo_action = self.action("Redo", self.redo, QKeySequence.StandardKey.Redo)
        self.toolbar.addSeparator()
        self.action("Details", self.details)
        self.toolbar.addSeparator()
        self.action("Export figure…", self.export_dialog, "Ctrl+E")
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(360)
        self.tabs.setMaximumWidth(450)
        self.build_structure_panel()
        self.viewport = Viewport(self.project)
        self.viewport.selectionChanged.connect(self.selection_changed)
        self.viewport.cameraChanged.connect(self.changed)
        self.composition_panel = CompositionPanel(self)
        self.appearance_panel = AppearancePanel(self)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(24, 20, 24, 12)
        self.title_label = heading(self.project.title)
        center_layout.addWidget(self.title_label)
        self.subtitle = heading("Ideal lattice · covalent radii · publication view", True)
        center_layout.addWidget(self.subtitle)
        viewbar = QHBoxLayout()
        for name in ("Top", "Side", "Isometric"):
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, n=name: self.viewport.preset(n))
            viewbar.addWidget(button)
        fit = QPushButton("Fit  ·  F")
        fit.clicked.connect(self.viewport.fit)
        viewbar.addWidget(fit)
        self.projection = QComboBox()
        self.projection.addItems(["Orthographic", "Perspective"])
        self.projection.currentTextChanged.connect(self.set_projection)
        viewbar.addWidget(self.projection)
        viewbar.addStretch()
        center_layout.addLayout(viewbar)
        center_layout.addWidget(self.viewport, 1)
        self.selection_label = heading(
            "Click an atom to inspect it. Ctrl/⌘-click adds sites.", True
        )
        center_layout.addWidget(self.selection_label)
        split = QSplitter()
        split.addWidget(self.tabs)
        split.addWidget(center)
        split.setSizes([375, 985])
        split.setCollapsible(0, False)
        split.setCollapsible(1, False)
        self.setCentralWidget(split)
        self.refresh()

    def action(self, text, slot, shortcut=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        self.toolbar.addAction(action)
        return action

    def build_structure_panel(self):
        scroll, layout, form = panel(
            "Create a surface",
            "Build an ideal ASE slab. Lattice parameters remain editable; "
            "all lengths are in ångströms.",
        )
        self.element = QLineEdit("Pt")
        self.element.setPlaceholderText("Pt, PtO, NiFe2O4…")
        self.crystal = QComboBox()
        self.crystal.addItems(["fcc", "bcc", "hcp", *PROTOTYPES])
        self.crystal.setToolTip(
            "A formula alone does not define a structure. "
            "Choose a crystal prototype or consult the compound examples."
        )
        self.structure_form = form
        self.miller = QLineEdit("1 0 0")
        self.miller.setToolTip("Three integer indices h k l. HCP uses ASE three-index notation.")
        self.lattice_a = decimal(3.92, 0.01, 100, " Å")
        self.lattice_c = decimal(6.4, 0.01, 100, " Å")
        self.lattice_c.setEnabled(False)
        self.nx, self.ny = integer(5, 1, 100), integer(5, 1, 100)
        self.layers = integer(4, 1, 200)
        self.vacuum = decimal(8, 0, 1000, " Å")
        self.internal_u = decimal(0.261, 0.001, 0.999, "", 5)
        self.inversion = decimal(1, 0, 1, "", 3)
        self.cation_seed = integer(42, 0, 2**31 - 1)
        self.cut_phase = decimal(0, 0, 0.999, "", 3)
        self.internal_u.setToolTip(
            "Fractional coordinate: rutile/wurtzite basis or spinel oxygen u."
        )
        self.inversion.setToolTip(
            "0 = normal, 1 = inverse. Explicit spinel cell realizes steps of 1/8."
        )
        self.cut_phase.setToolTip(
            "Shift the cut window by a fraction of one oriented cut-cell period. "
            "Phases within one plane gap can yield the same centered slab."
        )
        for label, widget in [
            ("Element / formula", self.element),
            ("Crystal / prototype", self.crystal),
            ("Miller (h k l)", self.miller),
            ("Lattice a", self.lattice_a),
            ("Lattice c", self.lattice_c),
            ("Internal coordinate u", self.internal_u),
            ("Spinel inversion", self.inversion),
            ("Cation ordering seed", self.cation_seed),
            ("Compound cut phase", self.cut_phase),
            ("Repeat along a", self.nx),
            ("Repeat along b", self.ny),
            ("Layers / cut repeats", self.layers),
            ("Vacuum · each side", self.vacuum),
        ]:
            form.addRow(label, widget)
        particles = QPushButton("Nanoparticle studio…")
        particles.clicked.connect(self.particle_dialog)
        layout.insertWidget(2, particles)
        examples = QPushButton("Compound examples and limits…")
        examples.clicked.connect(self.compound_examples)
        layout.insertWidget(2, examples)
        self.reference_button = QPushButton("Use ASE element reference")
        self.reference_button.clicked.connect(self.use_reference)
        layout.addWidget(self.reference_button)
        self.reference_note = heading(
            "Pt preset: a = 3.92 Å. Verify for your intended material.", True
        )
        layout.addWidget(self.reference_note)
        self.lattice_source = "Editable Pt reference preset (3.92 Å)"
        self.lattice_a.valueChanged.connect(self.lattice_edited)
        self.lattice_c.valueChanged.connect(self.lattice_edited)
        self.internal_u.valueChanged.connect(self.lattice_edited)
        self.element.textEdited.connect(self.lattice_edited)
        self.crystal.currentTextChanged.connect(self.crystal_changed)
        self.builder_note = heading("", True)
        layout.addWidget(self.builder_note)
        self.update_prototype_controls()
        self.structure_error = QLabel()
        self.structure_error.setProperty("role", "error")
        self.structure_error.setWordWrap(True)
        self.structure_error.hide()
        self.generate_button = QPushButton("Generate surface")
        self.generate_button.setProperty("primary", True)
        self.generate_button.clicked.connect(self.generate)
        layout.addStretch()
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll, 1)
        action_bar = QWidget()
        action_bar.setProperty("role", "actionbar")
        actions = QVBoxLayout(action_bar)
        actions.setContentsMargins(20, 12, 20, 16)
        actions.addWidget(self.structure_error)
        actions.addWidget(self.generate_button)
        outer.addWidget(action_bar)
        self.tabs.addTab(container, "Structure")

    def structure_message(self, message=""):
        self.structure_error.setText(message)
        self.structure_error.setVisible(bool(message))

    def lattice_edited(self, *args):
        self.lattice_source = "User-entered lattice/basis parameters"
        self.reference_note.setText(self.lattice_source)

    def crystal_changed(self, name):
        self.update_prototype_controls()
        self.miller.setText("0 0 1" if name == "hcp" or name in PROTOTYPES else "1 0 0")
        defaults = {"rutile": 0.305, "wurtzite": 0.375, "spinel": 0.261}
        if name in defaults:
            self.internal_u.setValue(defaults[name])
        self.lattice_edited()

    def update_prototype_controls(self):
        name = self.crystal.currentText()
        compound = name in PROTOTYPES
        self.lattice_c.setEnabled(name == "hcp" or name in C_AXIS_PROTOTYPES)
        self.structure_form.setRowVisible(
            self.lattice_c, name == "hcp" or name in C_AXIS_PROTOTYPES
        )
        self.structure_form.setRowVisible(self.internal_u, name in U_PROTOTYPES)
        self.structure_form.setRowVisible(self.inversion, name == "spinel")
        self.structure_form.setRowVisible(self.cation_seed, name == "spinel")
        self.structure_form.setRowVisible(self.cut_phase, compound)
        self.reference_button.setText(
            "Use matching compound preset" if compound else "Use ASE element reference"
        )
        if compound:
            self.builder_note.setText(
                PROTOTYPES[name][1] + ". Thickness counts full cut cells. "
                "Bulk ratios are preserved, but cuts can be polar/asymmetric. "
                "See examples for assumptions and limits."
            )
        else:
            self.builder_note.setText(
                "Low-index builders count atomic planes. Generic cuts count "
                "bulk-cell repeats; inspect the resulting plane count in Details."
            )

    def particle_dialog(self):
        from surfaces.particle_ui import ParticleDialog

        dialog = ParticleDialog(self)
        if dialog.exec() and dialog.project is not None:
            self.replace_generated(dialog.project)
        dialog.deleteLater()

    def compound_examples(self):
        dialog = CompoundExamplesDialog(self)
        if dialog.exec() and dialog.selected_example:
            self.apply_compound_example(dialog.selected_example)
        dialog.deleteLater()

    def apply_compound_example(self, example):
        self.fill_structure_controls(example.spec())
        self.structure_message()

    def use_reference(self):
        try:
            if self.crystal.currentText() in PROTOTYPES:
                formula, _ = parse_formula(self.element.text())
                example = next(
                    (
                        e
                        for e in EXAMPLES
                        if e.formula == formula and e.prototype == self.crystal.currentText()
                    ),
                    None,
                )
                if example is None:
                    raise ValueError(
                        "No catalog preset matches this formula/prototype. "
                        "Enter verified lattice/basis parameters or choose an example."
                    )
                self.lattice_a.setValue(example.a)
                if example.c:
                    self.lattice_c.setValue(example.c)
                self.internal_u.setValue(example.u)
                self.inversion.setValue(example.inversion)
                self.lattice_source = example.parameter_note
                self.reference_note.setText(example.parameter_note)
                self.structure_message()
                return
            reference = reference_lattice(self.element.text(), self.crystal.currentText())
            if reference is None:
                raise ValueError(
                    "ASE has no matching elemental reference for this crystal. "
                    "Enter a and, for HCP, c explicitly."
                )
            a, c, source = reference
            self.lattice_a.setValue(a)
            if c:
                self.lattice_c.setValue(c)
            self.lattice_source = source
            self.reference_note.setText(source)
            self.structure_message()
        except ValueError as exc:
            self.structure_message(str(exc))

    def generate(self):
        try:
            indices = tuple(int(n) for n in self.miller.text().replace(",", " ").split())
            if len(indices) != 3:
                raise ValueError("Enter three integer Miller indices, for example 1 0 0.")
            spec = StructureSpec(
                self.element.text().strip(),
                self.crystal.currentText(),
                indices,
                self.lattice_a.value(),
                self.lattice_c.value(),
                self.nx.value(),
                self.ny.value(),
                self.layers.value(),
                self.vacuum.value(),
                self.lattice_source,
                self.internal_u.value(),
                self.inversion.value(),
                self.cation_seed.value(),
                self.cut_phase.value(),
            )
            validate_spec(spec)
            self.structure_message()
            self.run_task(lambda: build_project(spec), self.replace_generated, "Building ASE slab…")
        except ValueError as exc:
            self.structure_message(str(exc))

    def replace_generated(self, project):
        self.record()
        representation = project.appearance.render_style
        project.appearance = copy.deepcopy(self.project.appearance)
        project.appearance.render_style = representation if project.mesh is not None else "atoms"
        project.export = copy.deepcopy(self.project.export)
        project.export_presets = copy.deepcopy(self.project.export_presets)
        if (
            not all(project.atoms.pbc[:2])
            or len(project.atoms) * project.appearance.copies_x * project.appearance.copies_y
            > 40_000
        ):
            project.appearance.copies_x = project.appearance.copies_y = 1
        self.project = project
        self.viewport.selected.clear()
        self.refresh()

    def commit_composition(self, result):
        atoms, operation = result
        self.record()
        self.project.atoms = atoms
        self.project.operations.append(operation)
        self.refresh()

    def run_task(self, function, callback, message):
        self.busy = True
        self.callback = callback
        self.centralWidget().setEnabled(False)
        self.toolbar.setEnabled(False)
        self.viewport.setEnabled(False)
        self.statusBar().showMessage(message)
        self.tasks.start(function)

    def task_result(self, result):
        self.callback(result)

    def task_idle(self):
        self.busy = False
        self.callback = None
        self.centralWidget().setEnabled(True)
        self.toolbar.setEnabled(True)
        self.viewport.setEnabled(True)
        self.refresh()
        if self.completed_message:
            self.statusBar().showMessage(self.completed_message, 15000)
            self.completed_message = None
        if self.after_idle:
            callback, self.after_idle = self.after_idle, None
            callback()

    def show_error(self, message):
        self.after_idle = None
        QMessageBox.warning(self, "Could not complete the operation", message)

    def export_dialog(self):
        dialog = ExportDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def record(self):
        self.undo_stack.append(copy.deepcopy(self.project))
        self.undo_stack = self.undo_stack[-30:]
        self.redo_stack.clear()
        self.dirty = True

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy(self.project))
            self.project = self.undo_stack.pop()
            self.viewport.selected.clear()
            self.dirty = True
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.project))
            self.project = self.redo_stack.pop()
            self.viewport.selected.clear()
            self.dirty = True
            self.refresh()

    def changed(self):
        self.dirty = True
        self.viewport.update()
        self.update_title()

    def update_title(self):
        self.setWindowTitle(f"{'● ' if self.dirty else ''}{self.project.title} — Surfaces")

    def set_projection(self, name):
        self.project.camera.projection = name
        self.changed()

    def refresh(self):
        self.viewport.project = self.project
        self.viewport.update()
        self.title_label.setText(self.project.title)
        source = "ASE ideal lattice" if self.project.spec else "Imported geometry"
        if self.project.spec and self.project.spec.particle:
            source = "Finite nanoparticle · unrelaxed"
        convention = "continuum surface" if not len(self.project.atoms) else "covalent radii"
        formula = self.project.atoms.get_chemical_formula()
        if not formula and self.project.mesh is not None:
            formula = self.project.mesh.element
        self.subtitle.setText(f"{source} · {convention} · {formula}")
        self.projection.blockSignals(True)
        self.projection.setCurrentText(self.project.camera.projection)
        self.projection.blockSignals(False)
        self.undo_action.setEnabled(bool(self.undo_stack))
        self.redo_action.setEnabled(bool(self.redo_stack))
        counts = Counter(self.project.atoms.get_chemical_symbols())
        total = len(self.project.atoms)
        summary = " · ".join(f"{s} {n} ({n / total:.1%})" for s, n in sorted(counts.items()))
        self.statusBar().showMessage(
            f"{total} atoms · {len(set(layer_indices(self.project.atoms)))} planes · {summary}"
        )
        self.selection_changed(self.viewport.selected)
        self.update_title()
        self.composition_panel.refresh()
        self.tabs.widget(1).setEnabled(bool(len(self.project.atoms)))
        if not len(self.project.atoms):
            self.selection_label.setText(
                "Continuum surface · no atoms generated. Rebuild with ASE atoms for site editing."
            )
            self.statusBar().showMessage(
                f"Continuum morphology · {len(self.project.mesh.faces):,} triangles "
                "· no atom count implied"
            )
        self.appearance_panel.refresh()
        self.sync_structure_form()

    def sync_structure_form(self):
        spec = self.project.spec
        signature = repr(asdict(spec)) if spec else None
        if signature == self.form_spec:
            return
        self.form_spec = signature
        if spec is None:
            self.reference_note.setText(
                "Imported structure; generation controls create a new slab."
            )
            return
        self.fill_structure_controls(spec)
        if spec.particle is not None:
            self.reference_note.setText(
                "Finite nanoparticle. Reopen Nanoparticle studio to edit its saved recipe; "
                "Generate surface below creates a new slab."
            )

    def fill_structure_controls(self, spec):
        controls = (
            self.element,
            self.crystal,
            self.miller,
            self.lattice_a,
            self.lattice_c,
            self.nx,
            self.ny,
            self.layers,
            self.vacuum,
            self.internal_u,
            self.inversion,
            self.cation_seed,
            self.cut_phase,
        )
        for widget in controls:
            widget.blockSignals(True)
        self.element.setText(spec.element)
        self.crystal.setCurrentText(spec.crystal)
        self.miller.setText(" ".join(map(str, spec.miller)))
        self.lattice_a.setValue(spec.a)
        if spec.c > 0:
            self.lattice_c.setValue(spec.c)
        self.internal_u.setValue(spec.internal_u)
        self.inversion.setValue(spec.inversion)
        self.cation_seed.setValue(spec.seed)
        self.cut_phase.setValue(spec.termination)
        self.nx.setValue(spec.nx)
        self.ny.setValue(spec.ny)
        self.layers.setValue(spec.layers)
        self.vacuum.setValue(spec.vacuum)
        self.lattice_source = spec.lattice_source
        self.reference_note.setText(spec.lattice_source)
        for widget in controls:
            widget.blockSignals(False)
        self.update_prototype_controls()

    def selection_changed(self, selected):
        if len(selected) == 1:
            ids = list(self.project.atoms.arrays["site_ids"])
            index = ids.index(next(iter(selected)))
            atom = self.project.atoms[index]
            layer = layer_indices(self.project.atoms)[index] + 1
            xyz = ", ".join(f"{n:.3f}" for n in atom.position)
            self.selection_label.setText(
                f"{atom.symbol} · site {ids[index]} · layer {layer} (bottom → top) · ({xyz}) Å"
            )
        else:
            self.selection_label.setText(
                f"{len(selected)} physical sites selected · periodic copies refer to the same site"
            )

    def details(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Structure details and provenance")
        dialog.resize(650, 500)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        atoms = self.project.atoms
        details = [
            self.project.title,
            "",
            f"Atoms: {len(atoms)}",
            f"Atomic planes (bottom → top): {len(set(layer_indices(atoms)))}",
            f"Periodic directions: {atoms.pbc.tolist()}",
            "",
            "Cell vectors (Å):",
            str(atoms.cell.array),
            "",
            "Provenance:",
        ]
        details.extend(f"{key}: {value}" for key, value in self.project.provenance.items())
        details.extend(["", "Composition history:"])
        for number, operation in enumerate(self.project.operations, 1):
            summary = {
                key: value
                for key, value in operation.items()
                if key not in ("assignments", "layers")
            }
            if "assignments" in operation:
                summary["assigned_sites"] = len(operation["assignments"])
            if "layers" in operation:
                summary["layer_recipes"] = [
                    {key: value for key, value in layer.items() if key != "assignments"}
                    for layer in operation["layers"]
                ]
            details.append(f"{number}. {summary}")
        details.extend(
            [
                "",
                "Construction recipe:",
                str(asdict(self.project.spec)) if self.project.spec else "Imported structure",
                "",
                "Display radius convention: ASE covalent radii with optional overrides.",
                "Species substitutions do not relax the lattice.",
                "Rendering: depth-sorted vector spheres; approximate overlapping occlusion.",
            ]
        )
        text.setPlainText("\n".join(details))
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        dialog.deleteLater()

    def save(self, checked=False, *, save_as=False, on_saved=None):
        path = self.path
        if save_as or not path:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Surfaces project",
                path or "surface.surfaces.json",
                "Surfaces project (*.surfaces.json)",
            )
            if not path:
                return
            if not path.endswith(".surfaces.json"):
                path += ".surfaces.json"
                if (
                    Path(path).exists()
                    and QMessageBox.question(
                        self, "Replace project?", f"Replace {Path(path).name}?"
                    )
                    != QMessageBox.StandardButton.Yes
                ):
                    return
        snapshot = copy.deepcopy(self.project)

        def saved(result):
            self.path = path
            self.dirty = False
            self.after_idle = on_saved
            self.update_title()

        self.run_task(lambda: save_project(snapshot, path), saved, "Saving project…")

    def protect_unsaved(self, callback):
        if not self.dirty:
            callback()
            return
        answer = QMessageBox.question(
            self,
            "Save your project?",
            "This project has unsaved changes.",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            self.save(on_saved=callback)
        elif answer == QMessageBox.StandardButton.Discard:
            callback()

    def open_project(self):
        def choose():
            path, _ = QFileDialog.getOpenFileName(
                self, "Open Surfaces project", "", "Surfaces project (*.surfaces.json *.json)"
            )
            if path:

                def opened(project):
                    self.project = project
                    self.path = path
                    self.undo_stack.clear()
                    self.redo_stack.clear()
                    self.viewport.selected.clear()
                    self.dirty = False
                    self.refresh()

                self.run_task(lambda: load_project(path), opened, "Reading project…")

        self.protect_unsaved(choose)

    def import_structure(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import structure with ASE",
            "",
            "Atomic structures (*.xyz *.extxyz *.cif *.traj *.vasp POSCAR CONTCAR);;All files (*)",
        )
        if path:
            self.run_task(
                lambda: import_project(path), self.replace_generated, "Importing structure…"
            )

    def closeEvent(self, event):
        if self.busy:
            self.statusBar().showMessage("Wait for the current operation to finish before closing.")
            event.ignore()
        else:
            if self.dirty:
                event.ignore()

                def finish():
                    self.dirty = False
                    self.close()

                self.protect_unsaved(finish)
            else:
                event.accept()
