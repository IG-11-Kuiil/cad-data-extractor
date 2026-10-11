"""Normalize CAD entities without guessing drawing semantics."""

from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import math
import logging

import ezdxf
from ezdxf.math import Vec2, Vec3

from .converter import ExtractionError, convert_dwg


class DiagnosticHandler(logging.Handler):
    def __init__(self, messages):
        super().__init__(logging.WARNING)
        self.messages = messages

    def emit(self, record):
        self.messages.append(f"DXF reader diagnostic: {record.getMessage()}")


def json_value(value):
    if isinstance(value, (Vec2, Vec3)):
        return [json_value(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return str(value)


def entity_record(entity, layout_name, warnings):
    kind = entity.dxftype()
    record = {
        "handle": entity.dxf.get("handle"), "type": kind,
        "layer": entity.dxf.get("layer", "0"), "layout": layout_name,
        "properties": {key: json_value(value) for key, value in entity.dxf.all_existing_dxf_attribs().items()},
    }
    if kind in {"TEXT", "ATTRIB", "ATTDEF"}:
        record["text"] = entity.dxf.text
    elif kind == "MTEXT":
        record["text"] = entity.plain_text()
        record["raw_text"] = entity.text
    elif kind == "INSERT":
        record["block_name"] = entity.dxf.name
        record["attributes"] = [
            {"handle": a.dxf.handle, "tag": a.dxf.tag, "text": a.dxf.text,
             "insert": json_value(a.dxf.insert)} for a in entity.attribs
        ]
    elif kind == "LWPOLYLINE":
        record["vertices"] = [list(point) for point in entity.get_points("xyseb")]
        record["closed"] = entity.closed
    elif kind == "POLYLINE":
        record["vertices"] = [json_value(vertex.dxf.location) for vertex in entity.vertices]
        record["closed"] = entity.is_closed
    elif kind == "DIMENSION":
        try:
            record["measurement"] = json_value(entity.get_measurement())
        except (ValueError, TypeError, ezdxf.DXFError) as exc:
            warnings.append(f"Dimension {entity.dxf.handle}: measurement unavailable: {exc}")
    return record


def extract_drawing(path: str | Path, *, converter: str | None = None) -> dict:
    source = Path(path).resolve()
    if not source.is_file():
        raise ExtractionError(f"Drawing does not exist: {source}")
    suffix = source.suffix.lower()
    if suffix not in {".dwg", ".dxf"}:
        raise ExtractionError("Expected a .dwg or .dxf drawing.")
    with TemporaryDirectory(prefix="cad-extract-") as directory:
        warnings = []
        readable = source
        if suffix == ".dwg":
            readable = Path(directory) / "converted.dxf"
            warnings.extend(convert_dwg(source, readable, converter) or [])
        logger = logging.getLogger("ezdxf")
        handler = DiagnosticHandler(warnings)
        logger.addHandler(handler)
        try:
            document = ezdxf.readfile(readable)
        except (OSError, ezdxf.DXFError, UnicodeError) as exc:
            raise ExtractionError(f"Cannot read drawing: {exc}") from exc
        finally:
            logger.removeHandler(handler)
        if suffix == ".dwg":
            warnings.append("DWG conversion can omit unsupported objects; validate against the source drawing.")
        records = []
        layouts = []
        for layout in document.layouts:
            layouts.append({"name": layout.name, "entity_count": len(layout)})
            for entity in layout:
                records.append(entity_record(entity, layout.name, warnings))
        blocks = []
        for block in document.blocks:
            if block.name.upper().startswith("*MODEL_SPACE") or block.name.upper().startswith("*PAPER_SPACE"):
                continue
            blocks.append({
                "name": block.name, "base_point": json_value(block.block.dxf.base_point),
                "flags": block.block.dxf.flags,
                "xref_path": block.block.dxf.get("xref_path", ""),
                "entities": [entity_record(e, f"block:{block.name}", warnings) for e in block],
            })
        xrefs = [b["name"] for b in blocks if b["flags"] & 12]
        if xrefs:
            warnings.append(f"External references are not loaded: {', '.join(xrefs)}")
        return {
            "schema_version": "1.0", "source": {"filename": source.name, "format": suffix[1:]},
            "drawing": {"dxf_version": document.dxfversion, "units_code": document.units,
                        "measurement_system": document.header.get("$MEASUREMENT", 0)},
            "summary": {"entity_count": len(records), "by_type": dict(Counter(e["type"] for e in records)),
                        "by_layer": dict(Counter(e["layer"] for e in records))},
            "layers": [{"name": layer.dxf.name, "color": layer.dxf.color,
                        "linetype": layer.dxf.linetype, "off": layer.is_off(),
                        "frozen": layer.is_frozen()} for layer in document.layers],
            "layouts": layouts, "entities": records, "blocks": blocks, "warnings": warnings,
        }
