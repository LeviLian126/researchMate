$ErrorActionPreference = "Stop"

$venvPath = "D:\software\researchMate\.venv"
if (-not (Test-Path $venvPath)) {
  python -m venv $venvPath
}

& "$venvPath\Scripts\python.exe" -m pip install -r requirements-dev.txt
& "$venvPath\Scripts\python.exe" -m pytest tests/test_project_scaffold.py -q
& "$venvPath\Scripts\python.exe" skill/agent-context-html/scripts/validate_context_dashboard.py docs/handoff

