"""Run the separately installed GNU LibreDWG converter."""

import shutil
import subprocess
from pathlib import Path


class ExtractionError(RuntimeError):
    """An actionable input or conversion failure."""


def convert_dwg(source: Path, destination: Path, executable: str | None = None) -> list[str]:
    command = shutil.which(executable or "dwg2dxf")
    if not command:
        raise ExtractionError(
            "DWG input requires GNU LibreDWG's dwg2dxf executable. "
            "Install LibreDWG, add it to PATH, or pass --converter PATH. "
            "Alternatively export the drawing as DXF."
        )
    try:
        result = subprocess.run(
            [command, "-o", str(destination), str(source)],
            capture_output=True, text=True, errors="replace", timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExtractionError(f"DWG conversion could not complete: {exc}") from exc
    if result.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        details = (result.stderr or result.stdout).strip()[-2000:]
        raise ExtractionError(f"DWG conversion failed (exit {result.returncode}): {details}")
    return [f"LibreDWG diagnostic: {line}" for line in result.stderr.strip().splitlines() if line.strip()]
