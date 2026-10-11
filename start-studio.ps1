param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& ./.venv/Scripts/python.exe -c 'import flask, cad_extractor'
if ($LASTEXITCODE -ne 0) {
    & ./.venv/Scripts/python.exe -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw 'Could not install CAD Studio.' }
}
& ./.venv/Scripts/python.exe -m cad_extractor.web --port $Port
