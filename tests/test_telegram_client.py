from __future__ import annotations

from gravelbot.config import Settings
from gravelbot.telegram.client import Telegram


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def _settings(monkeypatch, token="123:abc", chat_id="42"):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", chat_id)
    return Settings()


def test_telegram_disabled_without_credentials(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    tg = Telegram(Settings())
    assert tg.enabled is False
    assert tg.send("hallo") is None  # faellt auf print() zurueck, kein Netzwerk


def test_set_my_commands_sends_expected_payload(monkeypatch):
    tg = Telegram(_settings(monkeypatch))
    aufrufe = []

    def fake_post(url, json=None, timeout=None):
        aufrufe.append((url, json))
        return _FakeResponse(200, {"ok": True, "result": True})

    monkeypatch.setattr("gravelbot.telegram.client.requests.post", fake_post)

    ok = tg.set_my_commands([("start", "Bot kennenlernen"), ("help", "Hilfe anzeigen")])

    assert ok is True
    assert len(aufrufe) == 1
    url, payload = aufrufe[0]
    assert url.endswith("/setMyCommands")
    assert payload["commands"] == [
        {"command": "start", "description": "Bot kennenlernen"},
        {"command": "help", "description": "Hilfe anzeigen"},
    ]


def test_set_my_commands_returns_false_on_failure(monkeypatch):
    tg = Telegram(_settings(monkeypatch))
    monkeypatch.setattr(
        "gravelbot.telegram.client.requests.post",
        lambda url, json=None, timeout=None: _FakeResponse(401, {"ok": False}),
    )
    assert tg.set_my_commands([("start", "x")]) is False


def test_set_my_commands_without_credentials_does_not_call_network(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    tg = Telegram(Settings())

    def fail_if_called(*args, **kwargs):
        raise AssertionError("sollte ohne Token nicht aufgerufen werden")

    monkeypatch.setattr("gravelbot.telegram.client.requests.post", fail_if_called)
    assert tg.set_my_commands([("start", "x")]) is False
