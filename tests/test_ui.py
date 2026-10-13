import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt

from surfaces.app import configure_app
from surfaces.export_ui import ExportDialog
from surfaces.window import MainWindow


@pytest.fixture
def window(qtbot, qapp):
    configure_app(qapp)
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda widget: setattr(widget, "dirty", False))
    w.show()
    qtbot.waitUntil(lambda: bool(w.viewport.projected))
    yield w
    qtbot.waitUntil(lambda: not w.busy, timeout=10000)
    w.dirty = False


def test_alloy_apply_and_undo_redo_are_atomic(window, qtbot):
    panel = window.composition_panel
    panel.mode.setCurrentIndex(1)
    coordinates = window.project.atoms.positions.copy()
    panel.apply()
    assert not window.centralWidget().isEnabled()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.project.atoms.get_chemical_symbols().count("Au") == 30
    assert len(window.project.operations) == 1
    np.testing.assert_array_equal(window.project.atoms.positions, coordinates)
    window.undo()
    assert set(window.project.atoms.get_chemical_symbols()) == {"Pt"}
    window.redo()
    assert window.project.atoms.get_chemical_symbols().count("Au") == 30


def test_picking_frontmost_and_selected_assignment(window, qtbot):
    window.viewport.preset("Top")
    qtbot.wait(30)
    atom = window.viewport.projected[-1]
    scale = window.viewport.width() / 1000
    qtbot.mouseClick(
        window.viewport,
        Qt.MouseButton.LeftButton,
        pos=QPoint(round(atom.x * scale), round(atom.y * scale)),
    )
    assert window.viewport.selected == {atom.site_id}
    assert "layer" in window.selection_label.text()
    window.composition_panel.mode.setCurrentIndex(2)
    window.composition_panel.explicit_symbol.setText("Cu")
    window.composition_panel.apply()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.project.atoms.get_chemical_symbols().count("Cu") == 1


def test_export_preview_and_unit_conversion(window, qtbot):
    dialog = ExportDialog(window)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.export_button.isEnabled(), timeout=10000)
    assert dialog.preview.pixmap is not None
    dialog.unit.setCurrentText("in")
    assert dialog.width.value() == pytest.approx(6)
    dialog.transparent.setChecked(True)
    dialog.format.setCurrentText("SVG")
    qtbot.waitUntil(lambda: dialog.export_button.isEnabled(), timeout=10000)
    assert dialog.settings().transparent
    assert dialog.settings().format == "SVG"
    dialog.reject()
    qtbot.waitUntil(lambda: dialog.tasks.thread is None, timeout=10000)
    assert not dialog.isVisible()


def test_generation_changes_site_identity_and_undo_recovers_it(window, qtbot):
    old_ids = window.project.atoms.arrays["site_ids"].copy()
    window.nx.setValue(3)
    window.generate()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert len(window.project.atoms) == 60
    assert not set(old_ids) & set(window.project.atoms.arrays["site_ids"])
    window.undo()
    np.testing.assert_array_equal(window.project.atoms.arrays["site_ids"], old_ids)


def test_save_open_restore_state_and_recipe_controls(window, qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from surfaces.model import StructureSpec
    from surfaces.persistence import load_project, save_project
    from surfaces.structures import build_project

    path = tmp_path / "saved.surfaces.json"
    window.path = str(path)
    window.project.camera.azimuth = 78
    window.dirty = True
    window.save()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert not window.dirty
    assert load_project(path).camera.azimuth == 78
    imported = build_project(StructureSpec(element="Au", a=4.08, nx=3))
    save_project(imported, path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    window.open_project()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.element.text() == "Au"
    assert window.lattice_a.value() == pytest.approx(4.08)
    assert window.nx.value() == 3
    assert not window.dirty


def test_invalid_composition_is_inline_and_does_not_change_project(window):
    panel = window.composition_panel
    panel.mode.setCurrentIndex(1)
    panel.mixture_editor.table.cellWidget(0, 1).setValue(20)
    before = window.project.atoms.numbers.copy()
    panel.apply()
    assert "sum to 100" in panel.error.text()
    assert not window.busy
    np.testing.assert_array_equal(before, window.project.atoms.numbers)


def test_site_editor_reports_invalid_symbols(window):
    from surfaces.composition_ui import SiteDialog

    dialog = SiteDialog(window)
    assert not dialog.model.setData(dialog.model.index(0, 1), "Wrong")
    assert "Unknown element" in dialog.error.text()
    assert dialog.model.setData(dialog.model.index(0, 1), "Au")
    dialog.apply()
    assert window.project.atoms[0].symbol == "Au"
    window.undo()
    assert window.project.atoms[0].symbol == "Pt"
    dialog.deleteLater()


def test_composition_selector_opens_with_mouse(window, qtbot):
    window.tabs.setCurrentIndex(1)
    combo = window.composition_panel.mode
    qtbot.mouseClick(combo, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: combo.view().isVisible())
    index = combo.model().index(1, 0)
    qtbot.mouseMove(combo.view().viewport(), pos=combo.view().visualRect(index).center())
    qtbot.wait(20)
    qtbot.mouseClick(
        combo.view().viewport(),
        Qt.MouseButton.LeftButton,
        pos=combo.view().visualRect(index).center(),
    )
    qtbot.waitUntil(lambda: combo.currentText() == "Random alloy")


def test_selected_layer_scope_and_layer_recipes(window, qtbot):
    from surfaces.structures import layer_indices

    panel = window.composition_panel
    panel.mode.setCurrentIndex(1)
    panel.scope.setCurrentText("Selected layers")
    panel.layer_list.item(0).setSelected(True)
    panel.apply()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    planes = layer_indices(window.project.atoms)
    numbers = window.project.atoms.numbers
    assert np.count_nonzero(numbers[planes == 0] == 79) == 7
    assert np.count_nonzero(numbers[planes != 0] == 79) == 0
    panel.mode.setCurrentIndex(3)
    panel.recipes[3] = [("Cu", 100)]
    panel.apply()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert set(window.project.atoms.symbols[np.flatnonzero(planes == 3)]) == {"Cu"}


def test_compound_example_build_and_undo(window, qtbot):
    from surfaces.compounds import EXAMPLES

    window.apply_compound_example(EXAMPLES[0])
    assert window.crystal.currentText() == "cooperite"
    assert window.element.text() == "PtO"
    assert window.lattice_c.isEnabled()
    assert window.internal_u.isHidden()
    window.generate()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.project.atoms.get_chemical_symbols().count("Pt") == 16
    assert window.project.atoms.get_chemical_symbols().count("O") == 16
    assert window.project.spec.crystal == "cooperite"
    assert "Compound" in window.composition_panel.summary.text()
    window.undo()
    assert window.element.text() == "Pt"
    assert window.crystal.currentText() == "fcc"
    assert window.cut_phase.isHidden()


def test_inverse_spinel_controls_preset_and_build(window, qtbot):
    window.crystal.setCurrentText("spinel")
    window.element.setText("NiFe2O4")
    window.use_reference()
    assert window.inversion.value() == 1
    assert window.internal_u.value() == pytest.approx(0.261)
    assert not window.inversion.isHidden()
    assert not window.lattice_c.isEnabled()
    window.nx.setValue(1)
    window.ny.setValue(1)
    window.layers.setValue(1)
    window.generate()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert len(window.project.atoms) == 56
    assert window.project.provenance["tetrahedral_counts"] == {"Fe": 8}
    assert window.project.provenance["octahedral_counts"] == {"Ni": 8, "Fe": 8}


def test_compound_examples_search_and_choose(window, qtbot):
    from surfaces.compound_ui import CompoundExamplesDialog

    dialog = CompoundExamplesDialog(window)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.search.setText("NiFe2O4")
    assert dialog.list.count() == 1
    assert "56-atom" in dialog.description.toPlainText()
    assert "illustrative" in dialog.description.toPlainText().lower()
    dialog.choose()
    assert dialog.selected_example.formula == "NiFe2O4"
    window.apply_compound_example(dialog.selected_example)
    assert window.inversion.value() == 1
    assert window.nx.value() == 2
    assert window.layers.value() == 2


def test_formula_without_crystal_model_gets_actionable_error(window):
    window.element.setText("PtO")
    window.generate()
    assert "compound needs a crystal prototype" in window.structure_error.text().lower()
    assert not window.busy
    assert set(window.project.atoms.get_chemical_symbols()) == {"Pt"}
