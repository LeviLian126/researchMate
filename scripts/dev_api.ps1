$ErrorActionPreference = "Stop"

$venvPath = "D:\software\researchMate\.venv"
if (-not (Test-Path $venvPath)) {
  python -m venv $venvPath
}

& "$venvPath\Scripts\python.exe" -m pip install -r requirements-dev.txt
& "$venvPath\Scripts\python.exe" -m uvicorn researchmate_api.main:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000

