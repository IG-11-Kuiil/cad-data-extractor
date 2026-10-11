import json
from pathlib import Path
import subprocess

import ezdxf
import pytest

from cad_extractor import extract_drawing
from cad_extractor.cli import main
from cad_extractor.converter import ExtractionError, convert_dwg


@pytest.fixture
def drawing(tmp_path):
    document = ezdxf.new("R2018")
    document.units = 4
    document.layers.new("NOTES")
    model = document.modelspace()
    model.add_text("Pump P-101", dxfattribs={"layer": "NOTES"})
    model.add_mtext(r"First\PSecond")
    model.add_line((0, 0), (3, 4))
    model.add_lwpolyline([(0, 0), (10, 0), (10, 10)], close=True)
    model.add_linear_dim(base=(0, 2), p1=(0, 0), p2=(10, 0)).render()
    block = document.blocks.new("TITLE")
    block.add_attdef("DRAWING_NUMBER", insert=(0, 0))
    block.add_text("Title template")
    insert = document.layouts.get("Layout1").add_blockref("TITLE", (20, 30))
    insert.add_attrib("DRAWING_NUMBER", "A-101", (20, 30))
    path = tmp_path / "sample.dxf"
    document.saveas(path)
    return path


def test_extract_real_dxf(drawing):
    result = extract_drawing(drawing)
    assert result["drawing"]["units_code"] == 4
    assert result["summary"]["by_type"]["INSERT"] == 1
    assert result["summary"]["by_layer"]["NOTES"] == 1
    records = result["entities"]
    assert next(e for e in records if e["type"] == "MTEXT")["text"] == "First\nSecond"
    insert = next(e for e in records if e["type"] == "INSERT")
    assert insert["layout"] == "Layout1"
    assert insert["attributes"][0]["text"] == "A-101"
    assert next(e for e in records if e["type"] == "LINE")["properties"]["end"] == [3, 4, 0]
    assert next(e for e in records if e["type"] == "DIMENSION")["measurement"] == 10
    assert next(e for e in records if e["type"] == "LWPOLYLINE")["closed"]
    assert any(b["name"] == "TITLE" for b in result["blocks"])
    assert all(e["handle"] for e in records)
    json.dumps(result, allow_nan=False)


def test_cli_output_and_source_protection(drawing, tmp_path):
    output = tmp_path / "nested" / "result.json"
    assert main([str(drawing), "-o", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["source"]["filename"] == "sample.dxf"
    original = drawing.read_bytes()
    with pytest.raises(SystemExit):
        main([str(drawing), "-o", str(drawing)])
    assert drawing.read_bytes() == original


def test_bad_inputs(tmp_path, capsys):
    assert main([str(tmp_path / "missing.dwg")]) == 1
    assert "does not exist" in capsys.readouterr().err
    invalid = tmp_path / "bad.dxf"
    invalid.write_text("this is not DXF")
    with pytest.raises(ExtractionError, match="Cannot read"):
        extract_drawing(invalid)
    invalid = tmp_path / "bad.pdf"
    invalid.write_text("wrong extension")
    with pytest.raises(ExtractionError, match="Expected"):
        extract_drawing(invalid)


def test_missing_converter(tmp_path):
    with pytest.raises(ExtractionError, match="requires GNU LibreDWG"):
        convert_dwg(tmp_path / "input.dwg", tmp_path / "result.dxf", "no-such-converter-123")


def test_converter_failure_and_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("cad_extractor.converter.shutil.which", lambda _: "dwg2dxf")
    monkeypatch.setattr("cad_extractor.converter.subprocess.run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, "", "Invalid DWG"))
    with pytest.raises(ExtractionError, match="Invalid DWG"):
        convert_dwg(tmp_path / "input.dwg", tmp_path / "result.dxf")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("dwg2dxf", 120)
    monkeypatch.setattr("cad_extractor.converter.subprocess.run", timeout)
    with pytest.raises(ExtractionError, match="could not complete"):
        convert_dwg(tmp_path / "input.dwg", tmp_path / "result.dxf")


def test_dwg_pipeline(drawing, tmp_path, monkeypatch):
    """Exercise orchestration with a fixture converter, not native DWG parsing."""
    source = tmp_path / "drawing with spaces.dwg"
    source.write_bytes(b"AC1032")
    def convert(input_path, output_path, executable):
        output_path.write_bytes(drawing.read_bytes())
    monkeypatch.setattr("cad_extractor.extract.convert_dwg", convert)
    result = extract_drawing(source)
    assert result["source"]["format"] == "dwg"
    assert result["summary"]["entity_count"] > 0
    assert "conversion" in result["warnings"][0]
