# Validate core repository contracts with the pinned local Python environment.
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
& "$venvPath\Scripts\python.exe" -m pytest tests/test_project_scaffold.py tests/test_api_workflow.py tests/test_frontend_contracts.py -q
