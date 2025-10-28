# tests/conftest.py
import os
import sys

# path to the repo root (one level up from tests/)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ensure repo root is importable so `import src.*` works
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
