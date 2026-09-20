"""Telegram-API-Aufrufe. Reines I/O, kein Text-Rendering und keine Logik.

Der Bot laeuft als GitHub Action, nicht als Dauerprozess — es gibt also
keinen Webhook und kein Long-Polling im klassischen Sinn. Stattdessen holt
jeder Lauf per getUpdates alle Nachrichten seit dem zuletzt gespeicherten
offset (state.json) und beantwortet sie sofort. Ein /setup-Dialog zieht
sich dadurch ueber mehrere Cron-Laeufe (alle 30 Minuten) statt ueber
Sekunden — funktioniert, ist aber langsamer als ein Server mit Webhook.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from gravelbot.config import Settings

log = logging.getLogger("gravel.telegram")


class Telegram:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID fehlen — nur Log-Ausgabe")

    MAX_429_RETRIES = 3

    def _call(self, method: str, payload: dict, _retry: int = 0) -> dict | None:
        if not self.token:
            return None
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/{method}", json=payload, timeout=20
            )
        except requests.RequestException as exc:
            log.error("Telegram %s fehlgeschlagen: %s", method, exc)
            return None
        if resp.status_code == 429 and _retry < self.MAX_429_RETRIES:
            try:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
            except ValueError:
                retry_after = 5
            time.sleep(retry_after + 1)
            return self._call(method, payload, _retry=_retry + 1)
        if resp.status_code != 200:
            log.error("Telegram %s -> %s: %s", method, resp.status_code, resp.text[:300])
            return None
        return resp.json()

    def send(
        self,
        text: str,
        chat_id: str | None = None,
        preview: bool = True,
        keyboard: list[list[dict[str, str]]] | None = None,
    ) -> int | None:
        """Schickt eine Nachricht. Rueckgabe None heisst: nicht angekommen
        (z.B. Telegram-Fehler) — der Aufrufer kann daran entscheiden, ob er
        z.B. mark_alerted() trotzdem setzt oder es beim naechsten Lauf
        nochmal versucht."""
        target = chat_id or self.chat_id
        if not self.enabled:
            print(text)
            return None
        payload: dict[str, Any] = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": not preview},
        }
        if keyboard is not None:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        result = self._call("sendMessage", payload)
        if not result or not result.get("ok"):
            return None
        return result["result"]["message_id"]

    def edit_message(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        keyboard: list[list[dict[str, str]]] | None = None,
    ) -> bool:
        """Aendert eine bereits gesendete Nachricht in place, statt eine neue
        zu schicken. Wichtig fuer Dialogschritte mit Inline-Buttons (z.B.
        die Radtyp-Mehrfachauswahl in /setup): jeder Button-Tap sendet sonst
        eine komplett neue Nachricht, und bei mehreren schnellen Taps stapeln
        sich viele fast identische Nachrichten mit je einem anderen,
        eingefrorenen Auswahl-Stand — verwirrend und kaum nachvollziehbar,
        welche gerade aktuell ist."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard if keyboard is not None else []},
        }
        result = self._call("editMessageText", payload)
        return bool(result and result.get("ok"))

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        self._call("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

    def set_my_commands(self, commands: list[tuple[str, str]]) -> bool:
        """Registriert die Befehlsliste bei Telegram, damit sie als natives
        Menue erscheint (das '/'-Symbol im Nachrichtenfeld). Einmalig
        aufzurufen, z.B. per ``python bot.py --register-commands`` — nicht
        bei jedem Lauf, das waere ein unnoetiger API-Call fuer Daten, die
        sich praktisch nie aendern."""
        payload = {
            "commands": [{"command": cmd, "description": beschreibung} for cmd, beschreibung in commands]
        }
        result = self._call("setMyCommands", payload)
        return bool(result and result.get("ok"))

    def get_updates(self, offset: int) -> list[dict]:
        if not self.token:
            return []
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{self.token}/getUpdates",
                params={"offset": offset, "timeout": 0},
                timeout=20,
            )
        except requests.RequestException as exc:
            log.error("getUpdates fehlgeschlagen: %s", exc)
            return []
        if resp.status_code != 200:
            log.error("getUpdates -> %s: %s", resp.status_code, resp.text[:300])
            return []
        return list(resp.json().get("result") or [])
