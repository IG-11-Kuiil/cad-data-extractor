import argparse
import json
from pathlib import Path
import sys

from .converter import ExtractionError
from .extract import extract_drawing


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract DWG/DXF drawing data as JSON.")
    parser.add_argument("drawing", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path (default: stdout)")
    parser.add_argument("--converter", help="Path to GNU LibreDWG dwg2dxf")
    args = parser.parse_args(argv)
    if args.output and args.output.resolve() == args.drawing.resolve():
        parser.error("Output must not overwrite the source drawing.")
    try:
        data = extract_drawing(args.drawing, converter=args.converter)
        payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
    except (ExtractionError, OSError) as exc:
        print(f"cad-extract: {exc}", file=sys.stderr)
        return 1
    return 0
