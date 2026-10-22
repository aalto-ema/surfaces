"""Nanoparticle recipe editor with asynchronous, export-consistent preview."""

import copy

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from surfaces.model import ParticleSpec, StructureSpec
from surfaces.particles import FACET_SHAPES, LIMITS, SHAPES, validate_particle
from surfaces.rendering import Viewport
from surfaces.structures import build_project, reference_lattice
from surfaces.ui_common import Tasks, decimal, heading, integer, panel


class ParticleDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle("Nanoparticle studio")
        self.resize(1160, 860)
        self.setMinimumSize(940, 680)
        self.project = None
        self.valid = False
        self.dismiss_requested = False
        self.source = "User-entered parent lattice parameter"
        self.tasks = Tasks(self)
        self.tasks.result.connect(self.preview_ready)
        self.tasks.error.connect(self.preview_error)
        self.tasks.idle.connect(self.preview_idle)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.addWidget(heading("Nanoparticle studio"))
        outer.addWidget(
            heading("Define the parent crystal, choose a shape, then build a preview.", True)
        )
        split = QSplitter()
        outer.addWidget(split, 1)
        self.editor, layout, form = panel(
            "Shape & crystal", "Dimensions in Å · finite particles · no periodic copies"
        )
        self.editor.setMinimumWidth(360)
        self.editor.setMaximumWidth(440)
        split.addWidget(self.editor)
        self.form = form
        self.element = QLineEdit("Au")
        self.crystal = QComboBox()
        self.crystal.addItems(["fcc", "bcc", "sc"])
        self.a = decimal(4.08, 0.01, 100, " Å")
        self.padding = decimal(8, 0.1, 1000, " Å")
        self.shape = QComboBox()
        for key, label in SHAPES.items():
            self.shape.addItem(label, key)
        self.shells = integer(4, 1, 30)
        self.width = decimal(24, 0.1, 500, " Å")
        self.length = decimal(60, 0.1, 500, " Å")
        self.thickness = decimal(10, 0.1, 500, " Å")
        self.axis = QComboBox()
        self.axis.addItems(["001", "110", "111"])
        self.twist = decimal(120, -360, 360, "°", 1)
        self.target = integer(1000, 1, 20000)
        self.rounding = QComboBox()
        self.rounding.addItems(["closest", "above", "below"])
        self.unit = QComboBox()
        self.unit.addItems(["relative", "J/m²", "eV/Å²"])
        self.energy_source = QLineEdit(
            "Illustrative ratios; replace with verified surface energies"
        )
        self.illustrative = QCheckBox("Illustrative energies")
        self.illustrative.setChecked(True)
        for label, widget in [
            ("Element", self.element),
            ("Parent crystal", self.crystal),
            ("Lattice a", self.a),
            ("Cell padding · each side", self.padding),
            ("Shape", self.shape),
            ("Center → facet layers", self.shells),
            ("Width / diameter / side", self.width),
            ("Length · z", self.length),
            ("Thickness", self.thickness),
            ("Parent direction along z", self.axis),
            ("Signed total twist", self.twist),
            ("Target atoms", self.target),
            ("Size rounding", self.rounding),
            ("Energy units", self.unit),
            ("Energy source / assumptions", self.energy_source),
            ("", self.illustrative),
        ]:
            form.addRow(label, widget)
        for widget in (self.crystal, self.shape, self.axis, self.rounding, self.unit):
            widget.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            widget.setMinimumContentsLength(10)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for row in range(form.rowCount()):
            label = form.itemAt(row, form.ItemRole.LabelRole)
            if label and label.widget():
                label.widget().setWordWrap(True)
                label.widget().setFixedWidth(132)
        reference = QPushButton("Use ASE elemental reference")
        reference.clicked.connect(self.use_reference)
        layout.addWidget(reference)
        self.note = heading("", True)
        layout.addWidget(self.note)
        self.facets_box = QWidget()
        facet_layout = QVBoxLayout(self.facets_box)
        facet_layout.setContentsMargins(0, 0, 0, 0)
        facet_layout.addWidget(heading("Facet families"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["h k l", "Layers", "Energy"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(150)
        facet_layout.addWidget(self.table)
        buttons = QHBoxLayout()
        add = QPushButton("Add family")
        add.clicked.connect(lambda: self.add_facet([1, 1, 0], 6, 1.1))
        remove = QPushButton("Remove row")
        remove.clicked.connect(
            lambda: (self.table.removeRow(self.table.currentRow()), self.invalidate())
        )
        buttons.addWidget(add)
        buttons.addWidget(remove)
        facet_layout.addLayout(buttons)
        facet_layout.addWidget(
            heading(
                (
                    "Each row includes all cubic symmetry equivalents. Use reduced, "
                    "nonnegative indices 0–3. Layers count outward from the center; "
                    "Wulff uses energies instead."
                ),
                True,
            )
        )
        layout.addWidget(self.facets_box)
        layout.addWidget(heading(LIMITS, True))
        layout.addStretch()
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.viewport = Viewport(copy.deepcopy(window.project))
        right_layout.addWidget(self.viewport, 1)
        views = QHBoxLayout()
        for label in ("Top", "Side", "Isometric"):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, name=label: self.viewport.preset(name))
            views.addWidget(button)
        right_layout.addLayout(views)
        self.summary = heading(
            "Build a preview to inspect the atom count and actual dimensions.", True
        )
        right_layout.addWidget(self.summary)
        split.addWidget(right)
        split.setSizes([400, 720])
        self.error = heading("", True)
        self.error.setProperty("role", "error")
        outer.addWidget(self.error)
        actions = QHBoxLayout()
        self.build_button = QPushButton("Build preview")
        self.build_button.clicked.connect(self.build_preview)
        self.use_button = QPushButton("Use nanoparticle")
        self.use_button.setProperty("primary", True)
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(self.build_button)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(self.use_button)
        outer.addLayout(actions)
        self.fill(window.project.spec)
        for widget in (self.element, self.energy_source):
            widget.textChanged.connect(self.invalidate)
        for widget in (
            self.a,
            self.padding,
            self.shells,
            self.width,
            self.length,
            self.thickness,
            self.twist,
            self.target,
        ):
            widget.valueChanged.connect(self.invalidate)
        self.a.valueChanged.connect(
            lambda: setattr(self, "source", "User-entered parent lattice parameter")
        )
        self.element.textEdited.connect(self.parent_edited)
        self.crystal.currentIndexChanged.connect(self.parent_edited)
        for widget in (self.crystal, self.axis, self.rounding, self.unit):
            widget.currentIndexChanged.connect(self.invalidate)
        self.illustrative.toggled.connect(self.invalidate)
        self.table.itemChanged.connect(self.invalidate)
        self.shape.currentIndexChanged.connect(self.shape_changed)
        self.update_fields()
        self.build_preview()

    def parent_edited(self, *args):
        self.source = "User-entered parent lattice parameter; verify for selected element/crystal"

    def fill(self, spec):
        if spec and spec.particle is not None:
            p = spec.particle
            self.element.setText(spec.element)
            self.crystal.setCurrentText(spec.crystal)
            self.a.setValue(spec.a)
            self.padding.setValue(spec.vacuum)
            self.source = spec.lattice_source
        else:
            p = ParticleSpec()
            self.source = "Editable Au FCC preset: a = 4.08 Å; verify for intended material"
        self.shape.setCurrentIndex(self.shape.findData(p.shape))
        for widget, value in (
            (self.shells, p.shells),
            (self.width, p.width),
            (self.length, p.length),
            (self.thickness, p.thickness),
            (self.twist, p.twist),
            (self.target, p.target_atoms),
        ):
            widget.setValue(value)
        self.axis.setCurrentText(p.axis)
        self.rounding.setCurrentText(p.rounding)
        self.unit.setCurrentText(p.energy_unit)
        self.energy_source.setText(p.energy_source)
        self.illustrative.setChecked(p.illustrative)
        for row in p.facets:
            self.add_facet(row["miller"], row["layers"], row["energy"])

    def add_facet(self, miller, layers, energy):
        row = self.table.rowCount()
        if row >= 12:
            return
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(" ".join(map(str, miller))))
        self.table.setItem(row, 1, QTableWidgetItem(str(layers)))
        self.table.setItem(row, 2, QTableWidgetItem(str(energy)))
        self.invalidate()

    def invalidate(self, *args):
        self.valid = False
        self.use_button.setEnabled(False)
        self.summary.setText("Recipe changed · build a new preview before using this particle.")

    def shape_changed(self):
        if self.shape.currentData() in ("triangle", "hexagon"):
            self.axis.setCurrentText("111")
        self.update_fields()
        self.invalidate()

    def update_fields(self):
        shape = self.shape.currentData()
        faceted = shape in FACET_SHAPES
        wulff = shape == "wulff"
        for widget, visible in [
            (self.shells, shape in ("cube", "octahedron", "cuboctahedron")),
            (self.width, not faceted),
            (self.length, not faceted and shape not in ("sphere", "triangle", "hexagon")),
            (self.thickness, not faceted and shape not in ("sphere", "rod")),
            (self.axis, not faceted),
            (self.twist, shape in ("twisted_rod", "helicoid")),
            (self.target, wulff),
            (self.rounding, wulff),
            (self.unit, wulff),
            (self.energy_source, wulff),
            (self.illustrative, wulff),
        ]:
            self.form.setRowVisible(widget, visible)
        self.facets_box.setVisible(shape in ("facets", "wulff"))
        self.table.setColumnHidden(1, wulff)
        self.table.setColumnHidden(2, not wulff)
        notes = {
            "cube": (
                "Six {100} faces, e.g. an Au cube with Au(100) faces. Layer count "
                "is center-to-face, not total thickness."
            ),
            "octahedron": "Eight {111} faces, referenced to the conventional cubic parent cell.",
            "cuboctahedron": (
                "FCC cuboctahedron with {100} squares and {111} triangles. One "
                "shell parameter sets both layer counts."
            ),
            "wulff": (
                "Supply consistent positive energy-per-area values or explicit "
                "illustrative ratios. Only their ratios affect shape; whole "
                "layers make target sizes approximate."
            ),
            "triangle": (
                "Single-crystal triangular prism: width is equilateral side "
                "length, thickness is along z. [111] gives {111} broad faces. No "
                "twin planes are introduced."
            ),
            "hexagon": (
                "Width is vertex-to-vertex diameter; thickness is along z. [111] "
                "gives {111} broad faces."
            ),
            "twisted_rod": (
                "Rectangular rod, width × thickness × length, then continuously "
                "twisted around z. Positive twist follows the right-hand rule. "
                "This strains the parent lattice; inspect minimum distances."
            ),
            "helicoid": (
                "Rotating rectangular ribbon envelope, width × thickness, over "
                "length z. Atoms stay on the parent lattice; staircase boundaries "
                "approximate the helicoid. Positive twist is right-handed."
            ),
            "ellipsoid": "Full diameters: width along x, thickness along y, length along z.",
            "prism": (
                "Rectangular cross section: width along x, thickness along y, "
                "length along z. With [001], the bounding faces are {100}."
            ),
            "rod": (
                "Circular cross section of given diameter and axial length; "
                "end-cap normal follows the chosen parent direction."
            ),
            "sphere": (
                "Diameter bounds atom centers in an undeformed parent lattice. "
                "Curved surfaces contain terraces and steps, not one Miller facet."
            ),
            "facets": (
                "ASE intersects the selected cubic facet families. Layers specify "
                "center-to-plane counts; this does not determine thermodynamic "
                "stability."
            ),
        }
        self.note.setText(notes[shape])
        self.shape.setToolTip(SHAPES[shape])

    def use_reference(self):
        try:
            result = reference_lattice(self.element.text().strip(), self.crystal.currentText())
            if result is None:
                raise ValueError(
                    "No ASE reference matches this element/crystal; enter a verified "
                    "lattice constant."
                )
            a, _, source = result
            self.a.setValue(a)
            self.source = source
            self.error.setText(source)
        except ValueError as exc:
            self.error.setText(str(exc))

    def recipe(self):
        rows = []
        try:
            for row in range(self.table.rowCount()):
                rows.append(
                    {
                        "miller": [
                            int(i) for i in self.table.item(row, 0).text().replace(",", " ").split()
                        ],
                        "layers": int(self.table.item(row, 1).text()),
                        "energy": float(self.table.item(row, 2).text()),
                    }
                )
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                "Each facet row needs integer h k l, integer layers and a numeric energy."
            ) from exc
        p = ParticleSpec(
            shape=self.shape.currentData(),
            shells=self.shells.value(),
            width=self.width.value(),
            length=self.length.value(),
            thickness=self.thickness.value(),
            axis=self.axis.currentText(),
            twist=self.twist.value(),
            target_atoms=self.target.value(),
            rounding=self.rounding.currentText(),
            energy_unit=self.unit.currentText(),
            energy_source=self.energy_source.text().strip(),
            illustrative=self.illustrative.isChecked(),
            facets=rows,
        )
        spec = StructureSpec(
            element=self.element.text().strip(),
            crystal=self.crystal.currentText(),
            a=self.a.value(),
            vacuum=self.padding.value(),
            lattice_source=self.source,
            particle=p,
        )
        validate_particle(spec)
        return spec

    def build_preview(self):
        if self.tasks.thread is not None:
            return
        try:
            spec = self.recipe()
        except ValueError as exc:
            self.preview_error(str(exc))
            return
        self.valid = False
        self.use_button.setEnabled(False)
        self.editor.setEnabled(False)
        self.build_button.setEnabled(False)
        self.set_status_error(False)
        self.error.setText("Building ASE nanoparticle…")
        self.tasks.start(lambda: build_project(spec))

    def preview_ready(self, project):
        self.project = project
        self.viewport.project = project
        self.viewport.fit()
        dims = np.ptp(project.atoms.positions, axis=0)
        p = project.spec.particle
        count = f"{len(project.atoms):,} atoms"
        if p.shape == "wulff":
            count += f" · requested {p.target_atoms:,} ({p.rounding})"
        distance = project.provenance["minimum_distance_angstrom"]
        self.summary.setText(
            count
            + "\nActual atom-center spans: "
            + " × ".join(f"{v:.2f}" for v in dims)
            + " Å\nFinite, nonperiodic · "
            + (f"minimum separation {distance:.3f} Å" if distance else "single atom")
        )
        self.error.setText(
            "Ideal geometry · unrelaxed"
            + (" · illustrative energies" if p.shape == "wulff" and p.illustrative else "")
        )
        self.valid = True

    def set_status_error(self, is_error):
        self.error.setProperty("role", "error" if is_error else "muted")
        self.error.style().unpolish(self.error)
        self.error.style().polish(self.error)

    def preview_error(self, message):
        self.set_status_error(True)
        self.valid = False
        self.use_button.setEnabled(False)
        self.error.setText(message)

    def preview_idle(self):
        self.editor.setEnabled(True)
        self.build_button.setEnabled(True)
        self.use_button.setEnabled(self.valid)
        if self.dismiss_requested:
            super().reject()

    def accept(self):
        if self.valid and self.tasks.thread is None:
            super().accept()

    def reject(self):
        if self.tasks.thread is not None:
            self.dismiss_requested = True
        else:
            super().reject()

    def closeEvent(self, event):
        if self.tasks.thread is not None:
            self.dismiss_requested = True
            event.ignore()
        else:
            event.accept()
