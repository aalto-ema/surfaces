"""Appearance controls that leave scientific coordinates untouched."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from surfaces.rendering import element_color
from surfaces.ui_common import decimal, heading, integer, panel


class AppearancePanel:
    def __init__(self, window):
        self.window = window
        scroll, layout, form = panel(
            "Style the figure",
            "ASE covalent radii are the default visual convention. Override individual "
            "radii and colors without changing the lattice.",
        )
        self.scale = decimal(0.85, 0.1, 3, " ×", 2)
        form.addRow("Radius display scale", self.scale)
        self.background = QComboBox()
        self.background.addItems(["White", "Mist", "Dark slate", "Custom…"])
        self.background.currentIndexChanged.connect(self.choose_background)
        self.background_color = "#ffffff"
        form.addRow("Figure background", self.background)
        self.cell = QCheckBox("Show physical cell outline")
        self.axes = QCheckBox("Show Cartesian axes")
        self.legend = QCheckBox("Show element legend")
        self.outlines = QCheckBox("Subtle atom outlines")
        self.shading = QCheckBox("Sphere lighting")
        for widget in (self.cell, self.axes, self.legend, self.outlines, self.shading):
            layout.addWidget(widget)
        layout.addWidget(heading("Element appearance"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Element", "Radius · Å", "Color"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(140)
        self.table.setMaximumHeight(280)
        layout.addWidget(self.table)
        reset = QPushButton("Restore ASE radii and element colors")
        reset.clicked.connect(self.reset_elements)
        layout.addWidget(reset)
        layout.addWidget(heading("Periodic display copies"))
        self.copies_x = integer(1, 1, 5)
        self.copies_y = integer(1, 1, 5)
        form.addRow("Display copies · a", self.copies_x)
        form.addRow("Display copies · b", self.copies_y)
        layout.addWidget(
            heading(
                "Display copies are visual context only. Picking a copy selects "
                "its physical site; composition counts do not include copies.",
                True,
            )
        )
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setProperty("role", "error")
        layout.addWidget(self.error)
        apply = QPushButton("Update appearance")
        apply.setProperty("primary", True)
        apply.clicked.connect(self.apply)
        layout.addWidget(apply)
        layout.addStretch()
        window.tabs.addTab(scroll, "Appearance")
        self.refresh()

    def choose_background(self, index):
        colors = ["#ffffff", "#f1f4f8", "#182332"]
        if index < 3:
            self.background_color = colors[index]
        else:
            color = QColorDialog.getColor(parent=self.window)
            if color.isValid():
                self.background_color = color.name()

    def refresh(self):
        from ase.data import atomic_numbers, covalent_radii

        appearance = self.window.project.appearance
        self.scale.setValue(appearance.radius_scale)
        for widget, value in [
            (self.cell, appearance.cell),
            (self.axes, appearance.axes),
            (self.legend, appearance.legend),
            (self.outlines, appearance.outlines),
            (self.shading, appearance.shading),
        ]:
            widget.setChecked(value)
        self.copies_x.setValue(appearance.copies_x)
        self.copies_y.setValue(appearance.copies_y)
        self.background.blockSignals(True)
        index = {"#ffffff": 0, "#f1f4f8": 1, "#182332": 2}.get(appearance.background, 3)
        self.background.setCurrentIndex(index)
        self.background.blockSignals(False)
        self.background_color = appearance.background
        symbols = sorted(set(self.window.project.atoms.get_chemical_symbols()))
        self.table.setRowCount(len(symbols))
        for row, symbol in enumerate(symbols):
            item = QTableWidgetItem(symbol)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)
            radius = appearance.radii.get(symbol, float(covalent_radii[atomic_numbers[symbol]]))
            self.table.setCellWidget(row, 1, decimal(radius, 0.01, 20, "", 3))
            button = QPushButton()
            self.set_button_color(button, element_color(self.window.project, symbol).name())
            button.clicked.connect(lambda checked=False, b=button: self.choose_color(b))
            self.table.setCellWidget(row, 2, button)

    def set_button_color(self, button, color):
        button.setProperty("elementColor", color)
        button.setText(color.upper())
        from PySide6.QtGui import QColor

        text = "#203149" if QColor(color).lightnessF() > 0.5 else "#ffffff"
        button.setStyleSheet(f"background: {color}; color: {text}; border: 1px solid #a8b6c8;")

    def choose_color(self, button):
        from PySide6.QtGui import QColor

        color = QColorDialog.getColor(QColor(button.property("elementColor")), self.window)
        if color.isValid():
            self.set_button_color(button, color.name())

    def reset_elements(self):
        self.window.record()
        self.window.project.appearance.radii.clear()
        self.window.project.appearance.colors.clear()
        self.window.refresh()

    def apply(self):
        project = self.window.project
        copies = self.copies_x.value() * self.copies_y.value()
        if len(project.atoms) * copies > 40_000:
            self.error.setText("Reduce display copies to keep the scene below 40,000 atoms.")
            return
        if copies > 1 and (not project.atoms.pbc[0] or not project.atoms.pbc[1]):
            self.error.setText("Display repetition requires periodic a and b directions.")
            return
        self.error.clear()
        self.window.record()
        appearance = project.appearance
        appearance.radius_scale = self.scale.value()
        appearance.background = self.background_color
        appearance.cell = self.cell.isChecked()
        appearance.axes = self.axes.isChecked()
        appearance.legend = self.legend.isChecked()
        appearance.outlines = self.outlines.isChecked()
        appearance.shading = self.shading.isChecked()
        appearance.copies_x = self.copies_x.value()
        appearance.copies_y = self.copies_y.value()
        for row in range(self.table.rowCount()):
            symbol = self.table.item(row, 0).text()
            appearance.radii[symbol] = self.table.cellWidget(row, 1).value()
            appearance.colors[symbol] = self.table.cellWidget(row, 2).property("elementColor")
        self.window.refresh()
