"""Render the FastAPI schema and write or verify the tracked OpenAPI artifact."""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from researchmate_api.config import Settings
from researchmate_api.main import create_app


def rendered_schema() -> str:
    """Render a deterministic YAML schema from the test-configured app."""
    app = create_app(Settings(app_env="test", llm_provider="fake"))
    return yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True)


def main() -> None:
    """Write the OpenAPI artifact or fail when the tracked copy is stale."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = ROOT / "infra/openapi/openapi.yaml"
    generated = rendered_schema()
    if args.check:
        if not destination.exists() or destination.read_text(encoding="utf-8") != generated:
            raise SystemExit("OpenAPI artifact is stale; run scripts/export_openapi.py")
        return
    destination.write_text(generated, encoding="utf-8")


if __name__ == "__main__":
    main()
