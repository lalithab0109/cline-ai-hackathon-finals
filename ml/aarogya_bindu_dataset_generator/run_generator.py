"""Convenience launcher: ``python run_generator.py <command> [options]``.

Equivalent to ``python -m aarogya_synth`` with ``src`` on the import path, so no
package installation is needed. See README.md for commands.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from aarogya_synth.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
