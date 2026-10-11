"""Create a synthetic drawing without distributing customer CAD files."""
from pathlib import Path

import ezdxf

path = Path("output/sample.dxf")
path.parent.mkdir(parents=True, exist_ok=True)
document = ezdxf.new("R2018")
document.units = 4
document.layers.new("EQUIPMENT")
model = document.modelspace()
model.add_text("Pump P-101", dxfattribs={"layer": "EQUIPMENT", "insert": (10, 15)})
model.add_circle((10, 10), 3, dxfattribs={"layer": "EQUIPMENT"})
model.add_linear_dim(base=(0, -5), p1=(0, 0), p2=(20, 0)).render()
block = document.blocks.new("TITLE_BLOCK")
block.add_attdef("DRAWING_NO", insert=(0, 0))
block.add_attdef("REVISION", insert=(0, -5))
insert = document.layouts.get("Layout1").add_blockref("TITLE_BLOCK", (100, 20))
insert.add_auto_attribs({"DRAWING_NO": "M-001", "REVISION": "A"})
document.saveas(path)
print(path)
