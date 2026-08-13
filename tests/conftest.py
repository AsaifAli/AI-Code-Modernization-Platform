"""Make the repository root and agent_service package importable in local/CI test runs."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
AGENT_SERVICE = ROOT / "agent_service"
for path in (ROOT, AGENT_SERVICE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
