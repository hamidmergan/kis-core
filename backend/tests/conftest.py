# backend/tests/conftest.py
import sys
from pathlib import Path

# Make 'src' package importable when running pytest from repo root or backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
