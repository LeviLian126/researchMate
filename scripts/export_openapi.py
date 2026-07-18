from pathlib import Path
import argparse
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from researchmate_api.config import Settings  # noqa: E402
from researchmate_api.main import create_app  # noqa: E402


def rendered_schema() -> str:
    app = create_app(Settings(app_env="test", llm_provider="fake"))
    return yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True)


def main() -> None:
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
