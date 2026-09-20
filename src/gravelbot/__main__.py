"""CLI-Einstiegspunkt.

python -m gravelbot [--dry-run] [--test-telegram] [--scan-only]
                    [--telegram-update] [--register-commands]
"""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument(
        "--telegram-update",
        action="store_true",
        help=(
            "genau ein Telegram-Update aus TELEGRAM_UPDATE_JSON verarbeiten "
            "(fuer den Webhook-Trigger, siehe telegram-update.yml)"
        ),
    )
    parser.add_argument(
        "--register-commands",
        action="store_true",
        help="Befehlsliste bei Telegram registrieren (natives '/'-Menue), einmalig noetig",
    )
    args = parser.parse_args()

    from gravelbot.app import handle_single_update, run
    from gravelbot.config import BOT_COMMANDS, Settings
    from gravelbot.telegram.client import Telegram

    if args.test_telegram:
        tg = Telegram(Settings())
        ok = tg.send("✅ Gravel Deal Bot ist verbunden.", preview=False) is not None or not tg.enabled
        print("Testnachricht verschickt" if ok else "Fehlgeschlagen — Token/Chat-ID pruefen")
        return 0 if ok else 1

    if args.register_commands:
        tg = Telegram(Settings())
        if not tg.enabled:
            print("Fehlgeschlagen — TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID pruefen")
            return 1
        ok = tg.set_my_commands(BOT_COMMANDS)
        print(
            "Befehle registriert — das '/'-Menue in Telegram zeigt sie jetzt an" if ok else "Fehlgeschlagen"
        )
        return 0 if ok else 1

    if args.telegram_update:
        rohdaten = os.environ.get("TELEGRAM_UPDATE_JSON", "")
        if not rohdaten:
            logging.getLogger("gravel").error("TELEGRAM_UPDATE_JSON fehlt oder ist leer")
            return 1
        try:
            update = json.loads(rohdaten)
        except json.JSONDecodeError:
            logging.getLogger("gravel").exception("TELEGRAM_UPDATE_JSON ist kein gueltiges JSON")
            return 1
        try:
            handle_single_update(update, dry_run=args.dry_run)
        except Exception:
            logging.getLogger("gravel").exception("Verarbeitung des Updates abgebrochen")
            return 1
        return 0

    try:
        run(dry_run=args.dry_run, scan_only=args.scan_only)
    except Exception:
        logging.getLogger("gravel").exception("Lauf abgebrochen")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
