# Validate core repository contracts with the pinned local Python environment.
param([switch]$InstallDependencies)

$ErrorActionPreference = "Stop"
# Resolve a local venv dynamically. Prefer $env:VIRTUAL_ENV when active, then
# a project-local .venv; fall back to creating ./.venv so the script is portable.
$venvPath = if ($env:VIRTUAL_ENV -and (Test-Path $env:VIRTUAL_ENV)) {
  $env:VIRTUAL_ENV
} elseif (Test-Path ".\.venv") {
  (Resolve-Path ".\.venv").Path
} else {
  python -m venv ".\.venv"
  (Resolve-Path ".\.venv").Path
}

if ($InstallDependencies) {
  $env:UV_PROJECT_ENVIRONMENT = $venvPath
  uv sync --frozen --all-packages --group dev
}
& "$venvPath\Scripts\python.exe" -m pytest tests/test_project_scaffold.py tests/test_api_workflow.py tests/test_frontend_contracts.py -q
