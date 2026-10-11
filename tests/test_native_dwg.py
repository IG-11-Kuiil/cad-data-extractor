"""Opt-in integration test using actual LibreDWG Windows/Linux executables."""
import os
from pathlib import Path
import subprocess

import ezdxf
import pytest

from cad_extractor import extract_drawing


@pytest.mark.skipif(not os.environ.get("LIBREDWG_BIN"), reason="Set LIBREDWG_BIN to enable native DWG integration")
def test_native_dwg_roundtrip(tmp_path):
    folder = Path(os.environ["LIBREDWG_BIN"])
    extension = ".exe" if os.name == "nt" else ""
    document = ezdxf.new("R2000")
    document.modelspace().add_text("Pump P-101")
    document.modelspace().add_circle((10, 10), 3)
    block = document.blocks.new("TITLE")
    block.add_attdef("DRAWING_NO")
    insert = document.modelspace().add_blockref("TITLE", (100, 20))
    insert.add_auto_attribs({"DRAWING_NO": "M-001"})
    dxf = tmp_path / "input with spaces.dxf"
    dwg = tmp_path / "input with spaces.dwg"
    document.saveas(dxf)
    subprocess.run([str(folder / f"dxf2dwg{extension}"), "-o", str(dwg), str(dxf)],
                   check=True, capture_output=True, timeout=120)
    result = extract_drawing(dwg, converter=str(folder / f"dwg2dxf{extension}"))
    assert any(e.get("text") == "Pump P-101" for e in result["entities"])
    assert any(e["type"] == "CIRCLE" and e["properties"]["radius"] == 3 for e in result["entities"])
    assert any(a["tag"] == "DRAWING_NO" and a["text"] == "M-001"
               for e in result["entities"] for a in e.get("attributes", []))
