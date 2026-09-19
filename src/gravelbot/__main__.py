"""CLI-Einstiegspunkt.

python -m gravelbot [--dry-run] [--test-telegram] [--scan-only]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gravel Deal Bot")
    parser.add_argument("--dry-run", action="store_true", help="nichts senden, nichts speichern")
    parser.add_argument("--test-telegram", action="store_true", help="nur eine Testnachricht schicken")
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Telegram-Befehle nicht verarbeiten, nur scannen und melden",
    )
    args = parser.parse_args()

    from gravelbot.app import run
    from gravelbot.config import Settings
    from gravelbot.telegram.client import Telegram

    if args.test_telegram:
        tg = Telegram(Settings())
        ok = tg.send("✅ Gravel Deal Bot ist verbunden.", preview=False) is not None or not tg.enabled
        print("Testnachricht verschickt" if ok else "Fehlgeschlagen — Token/Chat-ID pruefen")
        return 0 if ok else 1

    try:
        run(dry_run=args.dry_run, scan_only=args.scan_only)
    except Exception:
        logging.getLogger("gravel").exception("Lauf abgebrochen")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
