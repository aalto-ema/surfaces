import xml.etree.ElementTree as ET

import pytest
from PIL import Image
from pypdf import PdfReader

from surfaces.exporting import ExportDimensions, export_figure
from surfaces.model import ExportSettings, StructureSpec
from surfaces.structures import build_project


@pytest.mark.parametrize("format,suffix", [("PNG", "png"), ("TIFF", "tiff")])
def test_raster_dimensions_alpha_and_dpi(qapp, tmp_path, format, suffix):
    p = build_project(StructureSpec())
    settings = ExportSettings(format=format, width=720, height=540, transparent=True)
    path = tmp_path / f"figure.{suffix}"
    export_figure(p, settings, path)
    with Image.open(path) as image:
        assert image.size == (720, 540)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        assert image.getchannel("A").getextrema() == (0, 255)
        assert image.info["dpi"][0] == pytest.approx(300, abs=1)
    settings.transparent = False
    export_figure(p, settings, path)
    with Image.open(path) as image:
        assert image.getpixel((0, 0)) == (255, 255, 255, 255)


def test_vector_sizes_and_no_embedded_images(qapp, tmp_path):
    p = build_project(StructureSpec())
    settings = ExportSettings(format="SVG", width=120, height=90, unit="mm", transparent=True)
    svg = tmp_path / "figure.svg"
    export_figure(p, settings, svg)
    root = ET.parse(svg).getroot()
    assert root.attrib["width"] == "120mm"
    assert root.attrib["height"] == "90mm"
    assert not any(node.tag.endswith("image") for node in root.iter())
    assert (
        sum(node.tag.rsplit("}", 1)[-1] in ("ellipse", "path", "circle") for node in root.iter())
        >= 100
    )
    settings.format = "PDF"
    pdf = tmp_path / "figure.pdf"
    export_figure(p, settings, pdf)
    page = PdfReader(pdf).pages[0]
    assert float(page.mediabox.width) == pytest.approx(120 / 25.4 * 72, abs=1)
    assert float(page.mediabox.height) == pytest.approx(90 / 25.4 * 72, abs=1)
    assert not list(page.images)


def test_physical_size_conversion_and_limits():
    settings = ExportSettings(width=2, height=1.5, unit="in", dpi=300)
    dims = ExportDimensions(settings)
    assert (dims.width_px, dims.height_px) == (600, 450)
    with pytest.raises(ValueError):
        ExportDimensions(ExportSettings(width=20000, height=20000))


@pytest.mark.parametrize("example_index", [0, 1], ids=["PtO", "NiFe2O4"])
@pytest.mark.parametrize("format", ["PNG", "TIFF", "PDF", "SVG"])
def test_compounds_export_all_formats(qapp, tmp_path, example_index, format):
    from surfaces.compounds import EXAMPLES

    p = build_project(EXAMPLES[example_index].spec())
    path = tmp_path / ("compound." + format.lower())
    settings = ExportSettings(format=format, width=480, height=360, transparent=True)
    export_figure(p, settings, path)
    if format in ("PNG", "TIFF"):
        with Image.open(path) as image:
            assert image.size == (480, 360)
            assert image.getchannel("A").getextrema() == (0, 255)
    elif format == "PDF":
        reader = PdfReader(path)
        assert len(reader.pages) == 1
        assert not list(reader.pages[0].images)
    else:
        root = ET.parse(path).getroot()
        assert not any(node.tag.endswith("image") for node in root.iter())
        labels = {node.text for node in root.iter() if node.tag.endswith("text")}
        assert set(p.atoms.get_chemical_symbols()) <= labels
