from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"

if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
