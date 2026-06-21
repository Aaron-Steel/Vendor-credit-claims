# Launch the Vendor Credit Claims app on http://127.0.0.1:8000
# First run: it auto-creates the DB and seeds reference data if needed.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

if (-not (Test-Path "data\app.db")) {
    Write-Host "Seeding database from template..."
    .\.venv\Scripts\python.exe scripts\extract_seed.py
    .\.venv\Scripts\python.exe -m app.seed
}

Write-Host "Starting app at http://127.0.0.1:8000  (Ctrl+C to stop)"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
