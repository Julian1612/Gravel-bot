#!/usr/bin/env python3
"""Duenner Einstiegspunkt — die eigentliche Logik steckt im gravelbot-Paket
unter src/gravelbot/. `python bot.py` bleibt so unveraendert nutzbar,
z.B. fuer scan.yml.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from gravelbot.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
