import sys
from pathlib import Path


# Ensure project package root (fastAPI-backend) is on sys.path so `import app` works
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

