from __future__ import annotations

from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.storage.store import Store
from gravelbot.telegram.router import Router


class _FakeTelegram:
    def __init__(self):
        self.enabled = True
        self.sent: list[tuple[str, str]] = []
        self.answered: list[str] = []

    def get_updates(self, offset: int) -> list[dict]:
        return self._updates

    def send(self, text, chat_id=None, preview=True, keyboard=None):
        self.sent.append((chat_id, text))
        return 1

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        self.answered.append(callback_query_id)


def _router(tmp_path, owner_chat_id="12345"):
    settings = Settings()
    object.__setattr__(settings, "telegram_chat_id", owner_chat_id)
    store = Store(str(tmp_path / "state.json"))
    telegram = _FakeTelegram()
    http = Http(settings)
    router = Router(telegram, store, http, settings, quellen=[])
    return router, telegram, store


def _text_update(update_id: int, chat_id: str, text: str) -> dict:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": int(chat_id)}, "text": text},
    }


def test_message_from_foreign_chat_is_ignored(tmp_path):
    router, telegram, store = _router(tmp_path, owner_chat_id="12345")
    telegram._updates = [_text_update(1, "99999", "/reset")]

    router.verarbeite_updates()

    assert telegram.sent == []
    assert store.telegram_offset == 2  # offset ruecken trotzdem vor, sonst haengt getUpdates


def test_message_from_owner_chat_is_processed(tmp_path):
    router, telegram, store = _router(tmp_path, owner_chat_id="12345")
    telegram._updates = [_text_update(1, "12345", "/profil")]

    router.verarbeite_updates()

    assert len(telegram.sent) == 1
    assert telegram.sent[0][0] == "12345"


def test_callback_from_foreign_chat_is_acknowledged_but_not_processed(tmp_path):
    router, telegram, store = _router(tmp_path, owner_chat_id="12345")
    profil = store.profil
    profil.max_distance_km = 999
    store.set_profil(profil)
    telegram._updates = [
        {
            "update_id": 1,
            "callback_query": {
                "id": "cq1",
                "data": "reset:ja",
                "message": {"chat": {"id": 99999}, "message_id": 1},
            },
        }
    ]

    router.verarbeite_updates()

    # Telegram erwartet immer eine Antwort auf callback_query, sonst haengt
    # der "Ladekreis" am Button beim Absender — aber es passiert nichts.
    assert telegram.answered == ["cq1"]
    assert telegram.sent == []
    assert store.profil.max_distance_km == 999  # kein Reset ausgeloest


def test_verarbeite_updates_is_noop_in_webhook_mode(tmp_path):
    router, telegram, store = _router(tmp_path, owner_chat_id="12345")
    object.__setattr__(router.settings, "telegram_webhook_mode", True)
    telegram._updates = [_text_update(1, "12345", "/profil")]

    router.verarbeite_updates()

    assert telegram.sent == []
    assert store.telegram_offset == 0  # get_updates wurde gar nicht erst aufgerufen


def test_verarbeite_ein_update_works_regardless_of_webhook_mode(tmp_path):
    router, telegram, store = _router(tmp_path, owner_chat_id="12345")
    object.__setattr__(router.settings, "telegram_webhook_mode", True)

    router.verarbeite_ein_update(_text_update(7, "12345", "/profil"))

    assert len(telegram.sent) == 1
    assert store.telegram_offset == 8
