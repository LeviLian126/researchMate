param([switch]$InstallDependencies)

$ErrorActionPreference = "Stop"
$venvPath = "D:\software\env\researchmate"
if (-not (Test-Path $venvPath)) {
  python -m venv $venvPath
}

if ($InstallDependencies) {
  uv pip install --python "$venvPath\Scripts\python.exe" -r requirements-dev.txt
}
& "$venvPath\Scripts\python.exe" -m pytest tests/test_project_scaffold.py tests/test_api_workflow.py tests/test_frontend_contracts.py -q
