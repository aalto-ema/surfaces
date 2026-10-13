"""Browsable, searchable compound examples with explicit model limits."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from surfaces.compounds import EXAMPLES, PROTOTYPES
from surfaces.ui_common import heading

LIMITS_HTML = """
<h3>Model limits</h3>
<ul>
<li>A formula does not determine a phase. Choose a prototype and verify its cell/basis.</li>
<li>All sites are fully occupied. Charges, magnetic order, relaxation, reconstruction,
    surface energies, electrostatic stability, and fractional occupancy are not calculated.</li>
<li>Compound thickness counts complete oriented bulk cells, not atomic planes.
    The slab retains the bulk element ratio; individual exposed planes can differ.</li>
<li>Cut phase shifts a complete-cell window through an ASE stack. Different phases
    within one inter-plane gap can give the same centered slab.
    Polar/asymmetric cuts are possible.</li>
<li>Spinel ordering uses one 56-atom parent cell repeated periodically. Inversion is rounded
    to steps of 1/8; Details reports the achieved value. Seeds choose explicit cation sites.</li>
<li>Numerical defaults are illustrative unless explicitly sourced. No stability or measured
    lattice constant is inferred for another formula with the same stoichiometry.</li>
<li>For another polymorph, lower symmetry, defects, or relaxed geometry, import a prepared,
    fully occupied slab (CIF/XYZ). Import reads the last frame; it does not cut a bulk CIF.</li>
<li>Radii remain ASE covalent radii, not oxidation-state-dependent ionic radii.
    Composition edits can change stoichiometry; use selected sites/layers deliberately.</li>
<li>20,000 physical atoms / 40,000 displayed atoms. Rendering uses vector spheres with
    approximate overlapping occlusion, not bond/electron-density or charge visualization.</li>
</ul>
"""


class CompoundExamplesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_example = None
        self.setWindowTitle("Compound examples and limits")
        self.resize(910, 710)
        layout = QVBoxLayout(self)
        layout.addWidget(heading("Compound examples"))
        layout.addWidget(
            heading(
                "Choose a formula and explicit crystal model. "
                "Use example fills the construction form; Generate builds it.",
                True,
            )
        )
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search formula or crystal prototype…")
        layout.addWidget(self.search)
        content = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(240)
        self.list.setMaximumWidth(310)
        self.description = QTextBrowser()
        self.description.setOpenExternalLinks(True)
        content.addWidget(self.list)
        content.addWidget(self.description, 1)
        layout.addLayout(content, 1)
        footer = QHBoxLayout()
        footer.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        self.use_button = QPushButton("Use example")
        self.use_button.setProperty("primary", True)
        self.use_button.clicked.connect(self.choose)
        footer.addWidget(self.use_button)
        layout.addLayout(footer)
        self.search.textChanged.connect(self.filter)
        self.list.currentItemChanged.connect(self.describe)
        self.filter("")

    def filter(self, text):
        self.list.clear()
        query = text.strip().casefold()
        for index, example in enumerate(EXAMPLES):
            if query in f"{example.formula} {example.prototype} {example.description}".casefold():
                item = QListWidgetItem(f"{example.formula}  ·  {example.prototype}")
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.list.addItem(item)
        self.use_button.setEnabled(bool(self.list.count()))
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.description.setHtml(
                "<p>No matching example. Other formulas may work with "
                "a matching prototype; no structure is guessed.</p>" + LIMITS_HTML
            )

    def describe(self, current, previous=None):
        if current is None:
            return
        example = EXAMPLES[current.data(Qt.ItemDataRole.UserRole)]
        parameters = f"a = {example.a:g} Å"
        if example.c:
            parameters += f"; c = {example.c:g} Å"
        if example.prototype in ("rutile", "wurtzite", "spinel"):
            parameters += f"; u = {example.u:g}"
        if example.prototype == "spinel":
            parameters += f"; inversion = {example.inversion:g}; seed = 42"
        self.description.setHtml(
            f"<h2>{escape(example.formula)} · {escape(example.prototype)}</h2>"
            f"<p>{escape(example.description)}</p>"
            f"<p><b>Basis:</b> {escape(PROTOTYPES[example.prototype][1])}</p>"
            f"<p><b>Starting parameters:</b> {parameters}</p>"
            f"<p>{escape(example.parameter_note)}</p>"
            f'<p><a href="{escape(example.source)}">Structure/model reference</a> '
            "(not a certificate of every numerical default)</p>" + LIMITS_HTML
        )

    def choose(self):
        item = self.list.currentItem()
        if item is not None:
            self.selected_example = EXAMPLES[item.data(Qt.ItemDataRole.UserRole)]
            self.accept()
