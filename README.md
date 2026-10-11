# CAD Data Extractor

A local Python CLI that extracts structured JSON from CAD drawings. DWG input
uses a separately installed GNU LibreDWG converter; DXF input is read directly
with ezdxf. Drawings are processed locally.

## Local UI

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\cad-studio.exe
```

Open **http://127.0.0.1:8765**. On Windows, `./start-studio.ps1` also sets up the
Python environment when needed. Use `--port 8766` with `cad-studio` to choose a
different port.

CAD Studio includes drag-and-drop DWG/DXF upload, a sample drawing, inventory
cards, searchable text and attributes, filters by layer/layout/type, an entity
property inspector, layer definitions, diagnostics, and JSON/CSV downloads.
CSV exports respect filters in the current data view. JSON exports contain the
complete extraction. Spreadsheet formula prefixes are escaped in CSV exports.

The geometry overview supports model-space lines, circles, and straight
lightweight polylines with standard XY extrusion. It omits other entities,
including block instances, curves, dimensions, and text, and reports the number
omitted. It is an overview rather than a full CAD viewer.

The server binds to loopback, accepts files up to 50 MB, and deletes uploaded
originals after processing. Extracted results remain in the browser session;
download them to keep a copy. LibreDWG is detected on PATH or at
`tools/libredwg/dwg2dxf.exe` in the current checkout. Set `CAD_CONVERTER` to an
executable path to override detection. This server is intended for local use.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe examples/make_sample.py
.\.venv\Scripts\cad-extract.exe output/sample.dxf -o output/sample.json
.\.venv\Scripts\python.exe -m pytest -q
```

## DWG input

Download and extract the Windows build from the
[official LibreDWG releases](https://github.com/LibreDWG/libredwg/releases).
Keep the executable with its DLLs, then add its folder to PATH or specify it:

```powershell
.\.venv\Scripts\cad-extract.exe drawing.dwg --converter C:\path\to\dwg2dxf.exe -o output/drawing.json
```

On Linux, install LibreDWG's `dwg2dxf` using your distribution's packages or
build it from the [official source](https://www.gnu.org/software/libredwg/).
The converter runs with a two-minute timeout and writes an intermediate DXF
inside a temporary folder that is removed after extraction. Original drawings
are read only.

## Extracted data

- Drawing format/version, units code, and model/paper layout inventory.
- Layer definitions and entity counts by type/layer.
- TEXT and MTEXT, including plain text for formatted MTEXT.
- Block references and attached attribute tags/values (useful for title blocks).
- Dimension measurements in drawing units and the original dimension properties.
- Entity properties such as coordinates, radii, angles, handles, and extrusion.
- Polyline vertices and block definitions, including text inside blocks.
- External reference paths and warnings when their contents are not loaded.

JSON includes `schema_version`, `source`, `drawing`, `summary`, `layers`,
`layouts`, `entities`, `blocks`, and `warnings`. Entity handles and layout names
provide traceability. Summary counts include top-level layout entities; block
definition entities are stored separately to avoid double-counting.

## Scope and limitations

This is structured extraction, not OCR or automatic engineering interpretation.
It does not yet identify drawing number/revision fields by inference, calculate
material takeoffs, expand block instances into world coordinates, or resolve
external reference files. Geometry properties retain their native coordinate
systems; INSERT transforms and extrusion must be applied by consumers.
Polyline bulges represent curved segments. Dimension measurements differ from
user-entered display overrides; the latter remain in the original properties.

DWG conversion can omit unsupported objects, especially custom/proxy objects.
Validate results against representative source drawings before relying on them.
The tests generate DXF fixtures; a mocked DWG test checks pipeline orchestration
and does not establish native DWG compatibility. The optional native integration
test converts a generated R2000 DXF to DWG and extracts it using real LibreDWG.
Enable it by setting `LIBREDWG_BIN` to the absolute converter folder:

```powershell
$env:LIBREDWG_BIN = (Resolve-Path tools/libredwg).Path
.\.venv\Scripts\python.exe -m pytest -q
```

Local validation used LibreDWG 0.14 (Windows x64) and ezdxf 1.4.4. Synthetic DWG
extraction retained equipment text, circle geometry, and title block attributes.
This does not establish compatibility with all AutoCAD versions or custom objects.
Converter stderr and DXF reader warnings are included in the JSON `warnings`.
The downloaded archive's SHA256 was
`1AD7E15344D20B3426C3435B078D82FB84B35062815946B2CCA9C5FC9810FEA8`.

## Open source components

- [ezdxf](https://ezdxf.readthedocs.io/en/stable/): MIT-licensed DXF reader.
- [GNU LibreDWG](https://www.gnu.org/software/libredwg/): GPLv3-or-later DWG reader
  and command-line converter. It is invoked as an external executable and is
  not bundled in this project's source repository.

Customer `.dwg`/`.dxf` inputs, local converter binaries, and generated output are
ignored by Git. Generate synthetic examples with `examples/make_sample.py`.
