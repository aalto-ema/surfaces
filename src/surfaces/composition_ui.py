"""Friendly composition recipes, layer assignments, and precise site editing."""

from collections import Counter, defaultdict

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from surfaces.composition import allocate, explicit, indices_for_ids, layered, substitute
from surfaces.compounds import PROTOTYPES
from surfaces.structures import layer_indices, validate_element
from surfaces.ui_common import decimal, heading, integer, panel


class MixtureEditor(QWidget):
    def __init__(self, mixture=None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Element", "Percent"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(125)
        self.table.setMaximumHeight(220)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        add = QPushButton("Add element")
        add.clicked.connect(lambda: self.add_row("", 0))
        remove = QPushButton("Remove row")
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        for symbol, percent in mixture or [("Pt", 70), ("Au", 30)]:
            self.add_row(symbol, percent)

    def add_row(self, symbol, percent):
        row = self.table.rowCount()
        self.table.insertRow(row)
        element = QLineEdit(symbol)
        element.setPlaceholderText("Pt, Au, Cu…")
        self.table.setCellWidget(row, 0, element)
        self.table.setCellWidget(row, 1, decimal(percent, 0, 100, " %", 3))
        self.table.setCurrentCell(row, 0)

    def mixture(self):
        return [
            (self.table.cellWidget(row, 0).text().strip(), self.table.cellWidget(row, 1).value())
            for row in range(self.table.rowCount())
        ]


class MixtureDialog(QDialog):
    def __init__(self, mixture, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Layer composition")
        self.resize(390, 320)
        layout = QVBoxLayout(self)
        layout.addWidget(heading("One element at 100%, or a mixture.", True))
        self.editor = MixtureEditor(mixture)
        layout.addWidget(self.editor)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setProperty("role", "error")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def check(self):
        from surfaces.composition import allocate

        try:
            allocate(1, self.editor.mixture())
            self.accept()
        except ValueError as exc:
            self.error.setText(str(exc))


class SiteModel(QAbstractTableModel):
    validationError = Signal(str)

    def __init__(self, atoms):
        super().__init__()
        self.atoms = atoms
        self.layers = layer_indices(atoms)
        self.assignments = {}
        self.ids = list(map(str, atoms.arrays["site_ids"]))

    def rowCount(self, parent=None):
        parent = QModelIndex() if parent is None else parent
        return 0 if parent.isValid() else len(self.atoms)

    def columnCount(self, parent=None):
        parent = QModelIndex() if parent is None else parent
        return 0 if parent.isValid() else 6

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ["Site ID", "Element", "Layer ↑", "x (Å)", "y (Å)", "z (Å)"][section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ):
            return None
        row, col = index.row(), index.column()
        if col == 0:
            return self.ids[row]
        if col == 1:
            return self.assignments.get(self.ids[row], self.atoms[row].symbol)
        if col == 2:
            return str(self.layers[row] + 1)
        return f"{self.atoms.positions[row, col - 3]:.4f}"

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 1:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or index.column() != 1:
            return False
        try:
            symbol = validate_element(str(value))
        except ValueError as exc:
            self.validationError.emit(str(exc))
            return False
        self.assignments[self.ids[index.row()]] = symbol
        self.validationError.emit("")
        self.dataChanged.emit(index, index)
        return True


class SiteDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Precise site editor")
        self.resize(850, 580)
        layout = QVBoxLayout(self)
        layout.addWidget(
            heading(
                "Select rows to select physical sites. Double-click an element "
                "to edit it; Apply commits all changes together.",
                True,
            )
        )
        self.model = SiteModel(window.project.atoms)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.error = QLabel()
        self.error.setProperty("role", "error")
        self.error.setWordWrap(True)
        self.model.validationError.connect(self.error.setText)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.table.selectionModel().selectionChanged.connect(self.select)

    def select(self, *args):
        ids = {self.model.ids[index.row()] for index in self.table.selectionModel().selectedRows()}
        self.window.viewport.selected = ids
        self.window.selection_changed(ids)
        self.window.viewport.update()

    def apply(self):
        if not self.model.assignments:
            return
        result = explicit(self.window.project.atoms, self.model.assignments)
        self.window.commit_composition(result)
        self.accept()


class LayerModel(QAbstractTableModel):
    def __init__(self, counts, recipes):
        super().__init__()
        self.counts = counts
        self.recipes = recipes

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.counts)

    def columnCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else 3

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ["Layer ↑", "Sites", "Composition · click to edit"][section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 2:
            return "Click to assign one element or a random mixture to this layer."
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        row = index.row()
        if index.column() == 0:
            return str(row + 1)
        if index.column() == 1:
            return str(self.counts[row])
        return " + ".join(f"{s} {p:g}%" for s, p in self.recipes[row]) + "  ›"


class CompositionPanel:
    def __init__(self, window):
        self.window = window
        scroll, self.layout, form = panel(
            "Define composition",
            "Assign species on the existing lattice. Operations replace only their target "
            "sites; geometry is never relaxed.",
        )
        self.mode = QComboBox()
        self.mode.addItems(
            ["Single element", "Random alloy", "Selected sites", "Layered structure"]
        )
        form.addRow("Mode", self.mode)
        self.scope = QComboBox()
        self.scope.addItems(["Whole slab", "Selected layers", "Selected sites"])
        form.addRow("Target scope", self.scope)
        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.layer_list.setMaximumHeight(125)
        self.layout.addWidget(self.layer_list)
        self.scope.currentTextChanged.connect(self.scope_changed)
        self.stack = QStackedWidget()
        self.stack.setMaximumHeight(280)
        single = QWidget()
        single_layout = QVBoxLayout(single)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.addWidget(heading("Element symbol", True))
        self.single = QLineEdit("Pt")
        single_layout.addWidget(self.single)
        single_layout.addStretch()
        self.stack.addWidget(single)
        self.mixture_editor = MixtureEditor()
        self.stack.addWidget(self.mixture_editor)
        selected = QWidget()
        selected_layout = QVBoxLayout(selected)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        selected_layout.addWidget(
            heading(
                "Click atoms in the viewport, or select rows in the site "
                "editor. All selected sites will receive this element.",
                True,
            )
        )
        self.explicit_symbol = QLineEdit("Au")
        selected_layout.addWidget(self.explicit_symbol)
        selected_layout.addStretch()
        self.stack.addWidget(selected)
        self.layer_table = QTableView()
        self.layer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.layer_table.setColumnWidth(0, 55)
        self.layer_table.setColumnWidth(1, 50)
        self.layer_table.verticalHeader().hide()
        self.layer_table.setMinimumHeight(180)
        self.layer_table.clicked.connect(
            lambda index: self.edit_layer(index.row()) if index.column() == 2 else None
        )
        self.stack.addWidget(self.layer_table)
        self.layout.addWidget(self.stack)
        self.seed = integer(42, 0, 2**31 - 1)
        form_seed = QHBoxLayout()
        form_seed.addWidget(QLabel("Random seed"))
        form_seed.addWidget(self.seed)
        self.layout.addLayout(form_seed)
        self.note = heading("", True)
        self.layout.addWidget(self.note)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setProperty("role", "error")
        self.layout.addWidget(self.error)
        self.apply_button = QPushButton("Apply composition")
        self.apply_button.setProperty("primary", True)
        self.apply_button.clicked.connect(self.apply)
        self.layout.addWidget(self.apply_button)
        sites = QPushButton("Open precise site editor…")
        sites.clicked.connect(self.open_sites)
        self.layout.addWidget(sites)
        reset = QPushButton("Reset to original species")
        reset.clicked.connect(self.reset)
        self.layout.addWidget(reset)
        self.summary = heading("", True)
        self.layout.addWidget(self.summary)
        self.layout.addStretch()
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.recipes = {}
        self.signature = None
        window.tabs.addTab(scroll, "Composition")
        self.refresh()
        self.mode_changed(0)

    def open_sites(self):
        dialog = SiteDialog(self.window)
        dialog.exec()
        dialog.deleteLater()

    def mode_changed(self, index):
        self.stack.setCurrentIndex(index)
        self.stack.setMaximumHeight([100, 280, 160, 280][index])
        self.scope.setEnabled(index < 2)
        self.seed.setEnabled(index in (1, 3))
        self.scope_changed(self.scope.currentText())
        self.note.setText(
            [
                "Replace the target scope with one element.",
                "Percentages must total 100%. Exact counts use largest-remainder rounding.",
                "Replace selected physical sites. Periodic copies share the same identity.",
                "Bottom → top. Click a composition to define one element or a random mixture. "
                "Layer seeds use seed + layer index. All listed layers will be replaced.",
            ][index]
        )
        self.error.clear()

    def scope_changed(self, text):
        self.layer_list.setVisible(text == "Selected layers" and self.mode.currentIndex() < 2)

    def refresh(self):
        atoms = self.window.project.atoms
        layers = layer_indices(atoms)
        signature = tuple(map(str, atoms.arrays["site_ids"]))
        if self.signature != signature:
            self.signature = signature
            self.recipes.clear()
            self.layer_list.clear()
            counts = np.bincount(layers)
            elements_by_layer = defaultdict(Counter)
            for symbol, layer in zip(atoms.get_chemical_symbols(), layers, strict=True):
                elements_by_layer[int(layer)][symbol] += 1
            for layer, count in enumerate(counts):
                item = QListWidgetItem(f"Layer {layer + 1} · {count} sites")
                item.setData(Qt.ItemDataRole.UserRole, layer)
                self.layer_list.addItem(item)
                self.recipes[layer] = [
                    (s, n / int(count) * 100) for s, n in elements_by_layer[layer].items()
                ]
            self.layer_model = LayerModel(counts, self.recipes)
            self.layer_table.setModel(self.layer_model)
            self.layer_table.setColumnWidth(0, 55)
            self.layer_table.setColumnWidth(1, 50)
            self.layer_table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeMode.Stretch
            )
        counts = Counter(atoms.get_chemical_symbols())
        self.summary.setText(
            "Current achieved composition\n"
            + "\n".join(f"{s}: {n} sites · {n / len(atoms):.2%}" for s, n in sorted(counts.items()))
        )
        if self.window.project.spec and self.window.project.spec.crystal in PROTOTYPES:
            self.summary.setText(
                self.summary.text() + "\n\nCompound: species edits can change "
                "stoichiometry and site chemistry. Select targets deliberately."
            )

    def update_layer_button(self, layer):
        index = self.layer_model.index(layer, 2)
        self.layer_model.dataChanged.emit(index, index)

    def edit_layer(self, layer):
        dialog = MixtureDialog(self.recipes[layer], self.window)
        if dialog.exec():
            self.recipes[layer] = dialog.editor.mixture()
            self.update_layer_button(layer)
        dialog.deleteLater()

    def target_ids(self):
        scope = self.scope.currentText()
        if scope == "Whole slab":
            return None
        if scope == "Selected sites":
            return set(self.window.viewport.selected)
        selected = {item.data(Qt.ItemDataRole.UserRole) for item in self.layer_list.selectedItems()}
        layers = layer_indices(self.window.project.atoms)
        return {
            str(value)
            for value, layer in zip(
                self.window.project.atoms.arrays["site_ids"], layers, strict=True
            )
            if layer in selected
        }

    def apply(self):
        atoms = self.window.project.atoms.copy()
        try:
            mode = self.mode.currentIndex()
            if mode == 0:
                mixture = [(self.single.text().strip(), 100)]
                ids = self.target_ids()
                allocate(len(atoms) if ids is None else len(indices_for_ids(atoms, ids)), mixture)

                def function():
                    return substitute(atoms, mixture, 0, ids)
            elif mode == 1:
                mixture = self.mixture_editor.mixture()
                ids, seed = self.target_ids(), self.seed.value()
                allocate(len(atoms) if ids is None else len(indices_for_ids(atoms, ids)), mixture)

                def function():
                    return substitute(atoms, mixture, seed, ids)
            elif mode == 2:
                assignments = dict.fromkeys(
                    self.window.viewport.selected, self.explicit_symbol.text().strip()
                )
                indices_for_ids(atoms, set(assignments))
                validate_element(self.explicit_symbol.text().strip())

                def function():
                    return explicit(atoms, assignments)
            else:
                recipes, seed = dict(self.recipes), self.seed.value()
                for mixture in recipes.values():
                    allocate(1, mixture)

                def function():
                    return layered(atoms, recipes, seed)

            self.error.clear()
            self.window.run_task(function, self.window.commit_composition, "Assigning species…")
        except ValueError as exc:
            self.error.setText(str(exc))

    def reset(self):
        if (
            QMessageBox.question(
                self.window,
                "Reset species?",
                "Restore original species on all sites? This can be undone.",
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.window.record()
            self.window.project.atoms = self.window.project.original.copy()
            self.window.project.operations.append({"kind": "reset_to_original"})
            self.window.refresh()
