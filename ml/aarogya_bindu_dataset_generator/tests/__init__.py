"""Test package. Puts ``src`` on sys.path so tests run without installing the package:

    python -m unittest discover -s tests -t .
"""

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
