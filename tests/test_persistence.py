import json

import numpy as np
import pytest

from surfaces.composition import substitute
from surfaces.model import StructureSpec
from surfaces.persistence import atomic_write, load_project, save_project, to_data
from surfaces.structures import build_project


def test_alloy_roundtrip_does_not_regenerate(tmp_path):
    p = build_project(StructureSpec())
    p.atoms, op = substitute(p.atoms, [("Pt", 65), ("Au", 35)], 87)
    p.operations.append(op)
    p.appearance.radii["Au"] = 1.4
    p.camera.azimuth = 123
    path = tmp_path / "test.surfaces.json"
    save_project(p, path)
    q = load_project(path)
    np.testing.assert_array_equal(p.atoms.numbers, q.atoms.numbers)
    np.testing.assert_array_equal(p.atoms.positions, q.atoms.positions)
    np.testing.assert_array_equal(p.atoms.arrays["site_ids"], q.atoms.arrays["site_ids"])
    assert p.operations == json.loads(json.dumps(q.operations))
    assert q.appearance.radii == p.appearance.radii
    assert q.camera == p.camera
    assert q.spec.miller == (1, 0, 0)


@pytest.mark.parametrize("change", ["version", "ids", "nan", "camera", "bool", "geometry"])
def test_malformed_projects_fail(tmp_path, change):
    data = to_data(build_project(StructureSpec()))
    if change == "version":
        data["schema_version"] = 9
    elif change == "ids":
        data["atoms"]["site_ids"][1] = data["atoms"]["site_ids"][0]
    elif change == "nan":
        data["atoms"]["positions"][0][0] = float("nan")
    elif change == "camera":
        data["camera"]["zoom"] = -1
    elif change == "bool":
        data["appearance"]["legend"] = "yes"
    else:
        data["atoms"]["positions"][0][0] += 1
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_project(path)


def test_failed_write_preserves_existing_file(tmp_path):
    path = tmp_path / "existing.json"
    path.write_text("previous content")

    def fail(target):
        target.write_text("partial")
        raise OSError("Simulated storage failure")

    with pytest.raises(OSError):
        atomic_write(path, fail)
    assert path.read_text() == "previous content"
    assert list(tmp_path.iterdir()) == [path]
