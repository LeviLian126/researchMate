# Start the local reloadable API with the pinned local Python environment.
param([switch]$InstallDependencies)

$ErrorActionPreference = "Stop"
$venvPath = "D:\software\env\researchmate"
if (-not (Test-Path $venvPath)) {
  python -m venv $venvPath
}

if ($InstallDependencies) {
  $env:UV_PROJECT_ENVIRONMENT = $venvPath
  uv sync --frozen --all-packages --group dev
}
& "$venvPath\Scripts\python.exe" -m uvicorn researchmate_api.main:app --reload --host 127.0.0.1 --port 8000
