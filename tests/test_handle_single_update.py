from __future__ import annotations

import json

from gravelbot.app import handle_single_update


def _env(monkeypatch, tmp_path, chat_id="12345"):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)  # Telegram bleibt "disabled", kein Netzwerk
    monkeypatch.setenv("TELEGRAM_CHAT_ID", chat_id)
    monkeypatch.setenv("STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)


def test_handle_single_update_processes_profil_command_without_scanning(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    update = {"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/profil"}}

    ergebnis = handle_single_update(update)

    assert ergebnis == 0
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["telegram_offset"] == 2


def test_handle_single_update_ignores_foreign_chat(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, chat_id="12345")
    update = {"update_id": 1, "message": {"chat": {"id": 99999}, "text": "/pause"}}

    handle_single_update(update)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    # /pause haette sofort paused=True gesetzt, wenn der Chat autorisiert waere
    assert state["profil"]["paused"] is False


def test_handle_single_update_does_not_scan_for_non_scan_commands(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    update = {"update_id": 5, "message": {"chat": {"id": 12345}, "text": "/markt"}}

    # Wenn hier ein echter Scan liefe, wuerde dieser Test Netzwerkzugriffe
    # brauchen und laenger als eine Web-Request-Antwortzeit dauern.
    ergebnis = handle_single_update(update)
    assert ergebnis == 0
