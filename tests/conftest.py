from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"
WORKER_SRC = ROOT / "workers/ai-worker/src"

if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))
