"""Pytest bootstrap.

Present so the project root is importable during collection regardless of how
pytest is invoked, and so a future fixture has an obvious home. ``pytest.ini``
sets ``pythonpath = .`` for the same reason; this file makes it work on older
pytest versions too.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
