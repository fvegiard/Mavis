# conftest.py — pytest config
# Allows running: cd /workspace/jarvis && python3 -m pytest tests/ -v

import sys
import os
from pathlib import Path

# Add scripts/ to sys.path so tests can import mavis-* modules
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
