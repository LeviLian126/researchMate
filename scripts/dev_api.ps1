param([switch]$InstallDependencies)

$ErrorActionPreference = "Stop"
$venvPath = "D:\software\env\researchmate"
if (-not (Test-Path $venvPath)) {
  python -m venv $venvPath
}

if ($InstallDependencies) {
  uv pip install --python "$venvPath\Scripts\python.exe" -r requirements-dev.txt
}
& "$venvPath\Scripts\python.exe" -m uvicorn researchmate_api.main:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000
