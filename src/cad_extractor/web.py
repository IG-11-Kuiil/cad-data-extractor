"""Loopback-only drawing explorer; uploaded originals are temporary."""
import argparse
import logging
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Lock

import ezdxf
from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from .converter import ExtractionError
from .extract import extract_drawing


def find_converter():
    configured = os.environ.get("CAD_CONVERTER")
    if configured:
        return shutil.which(configured)
    on_path = shutil.which("dwg2dxf")
    if on_path:
        return on_path
    local = Path.cwd() / "tools" / "libredwg" / "dwg2dxf.exe"
    return str(local.resolve()) if local.is_file() else None


def make_demo(path):
    doc = ezdxf.new("R2000")
    doc.units = 4
    for name, color in [("WALLS", 7), ("EQUIPMENT", 3), ("ANNOTATIONS", 2)]:
        doc.layers.new(name, dxfattribs={"color": color})
    model = doc.modelspace()
    for start, end in [((0, 0), (180, 0)), ((180, 0), (180, 110)),
                       ((180, 110), (0, 110)), ((0, 110), (0, 0)),
                       ((110, 0), (110, 110)), ((0, 55), (110, 55))]:
        model.add_line(start, end, dxfattribs={"layer": "WALLS"})
    for x, y, label in [(35, 28, "PUMP P-101"), (75, 28, "PUMP P-102"), (145, 78, "TANK T-201")]:
        model.add_circle((x, y), 10, dxfattribs={"layer": "EQUIPMENT"})
        model.add_text(label, dxfattribs={"insert": (x - 16, y - 19), "height": 3, "layer": "ANNOTATIONS"})
    model.add_lwpolyline([(20, 80), (80, 80), (80, 95), (20, 95)], close=True,
                         dxfattribs={"layer": "EQUIPMENT"})
    model.add_text("MECHANICAL ROOM", dxfattribs={"insert": (28, 62), "height": 4, "layer": "ANNOTATIONS"})
    model.add_linear_dim(base=(0, -12), p1=(0, 0), p2=(180, 0), dxfattribs={"layer": "ANNOTATIONS"}).render()
    block = doc.blocks.new("TITLE_BLOCK")
    for index, tag in enumerate(["DRAWING_NO", "PROJECT", "REVISION", "SHEET_TITLE"]):
        block.add_attdef(tag, insert=(0, -index * 5))
    ref = doc.layouts.get("Layout1").add_blockref("TITLE_BLOCK", (10, 30))
    ref.add_auto_attribs({"DRAWING_NO": "M-001", "PROJECT": "North plant upgrade", "REVISION": "A", "SHEET_TITLE": "Equipment layout"})
    doc.saveas(path)


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
    # ezdxf diagnostics use a process-wide logger; serialize parsing requests.
    extraction_lock = Lock()

    @app.before_request
    def local_requests_only():
        host = request.host.split(":")[0].lower()
        if host not in {"127.0.0.1", "localhost"}:
            return jsonify(error="Use the local application address."), 403
        if request.method == "POST":
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return jsonify(error="Upload from the local application."), 403

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/status")
    def status():
        return jsonify(dwg_available=bool(find_converter()), max_upload_mb=50)

    @app.post("/api/extract")
    def extract():
        upload = request.files.get("drawing")
        if upload is None or not upload.filename:
            return jsonify(error="Choose a DWG or DXF drawing."), 400
        name = secure_filename(upload.filename)
        if Path(name).suffix.lower() not in {".dwg", ".dxf"}:
            return jsonify(error="This file type is not supported. Choose DWG or DXF."), 400
        try:
            with TemporaryDirectory(prefix="cad-studio-") as directory:
                path = Path(directory) / name
                upload.save(path)
                with extraction_lock:
                    data = extract_drawing(path, converter=find_converter())
                return jsonify(data)
        except ExtractionError as exc:
            return jsonify(error=str(exc)), 422
        except Exception:
            app.logger.exception("Drawing extraction failed")
            return jsonify(error="This drawing could not be processed. Check the file and try again."), 500

    @app.get("/api/demo")
    def demo():
        with TemporaryDirectory(prefix="cad-studio-demo-") as directory:
            path = Path(directory) / "North-plant_M-001.dxf"
            with extraction_lock:
                make_demo(path)
                return jsonify(extract_drawing(path))

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return jsonify(error="This drawing exceeds the 50 MB upload limit."), 413

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the local CAD extraction studio.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    print(f"CAD Studio: http://127.0.0.1:{args.port}", flush=True)
    create_app().run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
