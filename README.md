# CAD Data Extractor

A local Python application with a browser UI and CLI that extracts structured
data from CAD drawings. DWG input
uses a separately installed GNU LibreDWG converter; DXF input is read directly
with ezdxf. Drawings are processed locally.

## What we have built

The first milestone is a working deterministic extraction pipeline: upload a
drawing, inspect its data, and export records that retain their source entity
handles, layers, and layouts. CAD Studio makes those records searchable without
requiring a CAD application for the first pass.

```text
DWG -> LibreDWG -> temporary DXF -> ezdxf -> structured records
DXF ------------------------------------> ezdxf -> structured records
                                                    |
                                             CAD Studio / CLI
                                                    |
                                                JSON / CSV
```

The broader goal is to test whether native CAD data adds useful information to
PDF plan sheets, then connect answers back to their source evidence. This version
implements the native drawing extraction and inspection portion. PDF extraction,
automatic DWG-to-PDF matching, and AI question answering are not implemented yet.

## Local UI

Requires Python 3.10 or newer. From a fresh checkout:

```powershell
python -m venv .venv
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

## Drawing comparisons completed

On October 11, 2026, we inspected two uploaded DWGs and manually compared their
extracted data with user-provided screenshots of PDF sheets. These were selected
content checks, not automated PDF comparisons or full drawing fidelity tests.
The source drawings and exported results are not bundled with this repository.

| Drawing | Extraction observed | Comparison result |
| --- | --- | --- |
| `SD-14.dwg` street section | 355 layout entities, 35 text entries, 22 layers, 5 block definitions; 5,900 diagnostics | Roadway widths (27 ft total, 13 ft 6 in halves, 11 ft 6 in portions), 5 ft sidewalk labels, 2 ft 6 in minimum utility strips, slope labels, curb note, and the three general notes matched the screenshot. |
| `floorplan.dwg` residential plans and elevation | 900 layout entities, 400 text/attribute entries including block definitions, 24 layers, 262 block definitions, 24 dimension entities; 1,514 diagnostics | Ground Floor, First Floor, and Front Elevation labels matched. Model-space text contained three ground-floor bedroom labels and two first-floor bedroom labels, all 11 ft x 15 ft; kitchen, living-room, balcony, and passage labels also matched the screenshot. |

### Differences found in SD-14

- The DWG labels the right-of-way as `45'-0" R/W`; the screenshot says
  `R/W VARIABLE WIDTH`.
- The DWG's extracted review date is `26 JAN 21`; the screenshot says `JULY 2024`.
- The DWG title includes `SECTION FOR RESIDENTIAL USE`; the screenshot's title
  ends with `SECTION`.

These differences suggest different revisions of the same detail. This pair
cannot establish extraction accuracy against an exact matching source revision.

### Additional checks on the floor plan

- The outer dimensions of both floor plans read 60 ft x 50 ft. Extracted CAD
  dimension measurements were 720 x 600 drawing units, and the units code was
  inches, consistent with those displayed dimensions.
- Room sizes were checked as labels; they were not independently calculated
  from room boundaries. Floor assignment used label positions relative to the
  floor titles and the screenshot, not a modeled room hierarchy.
- Searching all extracted text for `BEDROOM` returned nine entries. Only five
  were direct model-space bedroom labels; four came from block definitions.
  A text-search result count is not a room count.

The diagnostics included unsupported or unknown objects in SD-14 and flag,
attribute, and hatch issues in the floor plan. A diagnostic count is not a count
of lost visible objects. Successful label extraction does not prove that every
object, graphic, or property survived conversion.

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

## Next milestones

1. Obtain a DWG and PDF from the exact same revision, along with referenced
   drawings, and define a few questions to verify against them.
2. Add PDF text extraction with page coordinates and a viewer for checking
   candidate links between CAD records and PDF regions.
3. Normalize units and separate layout entities, block definitions, and placed
   block instances when answering counts or quantities.
4. Evaluate a richer Civil 3D export or API for modeled pipes, structures,
   alignments, and surfaces. The current pipeline has not demonstrated reliable
   extraction of those typed object properties.
5. Add interpretation for ambiguous notes and symbols after deterministic
   answers have been validated. Each answer should include its source scope,
   supporting record, and any missing data.

The next success criterion is a small set of accurate, traceable answers from a
matched drawing-and-sheet pair.
