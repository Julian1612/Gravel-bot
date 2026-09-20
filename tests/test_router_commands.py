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


def test_empty_text_message_does_not_crash(tmp_path):
    # Regression: text.split(maxsplit=1) auf "" ist [], und
    # cmd, *rest = [] wirft ValueError beim Entpacken.
    router, telegram, _ = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": ""}})
    assert len(telegram.sent) == 1  # faellt auf die Hilfe zurueck, statt zu crashen


def test_whitespace_only_message_does_not_crash(tmp_path):
    router, telegram, _ = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "   \n  "}})
    assert len(telegram.sent) == 1


def test_block_seller_callback_actually_blocks(tmp_path):
    router, telegram, store = _router(tmp_path)
    assert store.is_seller_blocked("radhaus_stuttgart") is False

    router.verarbeite_ein_update(
        {
            "update_id": 1,
            "callback_query": {
                "id": "cq1",
                "data": "blockliste:verkaeufer_sperren:radhaus_stuttgart",
                "message": {"chat": {"id": 12345}, "message_id": 1},
            },
        }
    )

    assert store.is_seller_blocked("radhaus_stuttgart") is True
    assert telegram.answered == ["cq1"]
    assert len(telegram.sent) == 1


def test_unblock_seller_callback_reverses_it(tmp_path):
    router, telegram, store = _router(tmp_path)
    store.block_seller("radhaus_stuttgart")

    router.verarbeite_ein_update(
        {
            "update_id": 1,
            "callback_query": {
                "id": "cq1",
                "data": "blockliste:verkaeufer_entsperren:radhaus_stuttgart",
                "message": {"chat": {"id": 12345}, "message_id": 1},
            },
        }
    )

    assert store.is_seller_blocked("radhaus_stuttgart") is False


def test_pause_toggles_profil(tmp_path):
    router, telegram, store = _router(tmp_path)
    assert store.profil.paused is False

    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/pause"}})
    assert store.profil.paused is True

    router.verarbeite_ein_update({"update_id": 2, "message": {"chat": {"id": 12345}, "text": "/pause"}})
    assert store.profil.paused is False


def test_scan_command_sets_scan_erzwingen_flag(tmp_path):
    router, telegram, store = _router(tmp_path)
    assert router.scan_erzwingen is False

    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/scan"}})

    assert router.scan_erzwingen is True


def test_bare_help_without_slash_shows_help(tmp_path):
    router, telegram, _ = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "help"}})
    assert "Gravel Deal Bot" in telegram.sent[0][1]


def test_bare_hilfe_shows_help(tmp_path):
    router, telegram, _ = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "Hilfe"}})
    assert "Gravel Deal Bot" in telegram.sent[0][1]


def test_start_command_shows_welcome(tmp_path):
    router, telegram, _ = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/start"}})
    assert "Willkommen" in telegram.sent[0][1]


def test_command_with_bot_username_suffix_is_recognized(tmp_path):
    # Manche Telegram-Clients haengen den Bot-Usernamen an, z.B. in Gruppen.
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update(
        {"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/pause@gravel_deal_bot"}}
    )
    assert store.profil.paused is True


def test_bare_command_without_leading_slash_still_works(tmp_path):
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "pause"}})
    assert store.profil.paused is True


def test_help_escapes_a_stuck_dialog(tmp_path):
    # Regression fuer den Kernbug: mitten in /setup blieb JEDE Nachricht,
    # inklusive /help, im Dialog haengen — "bitte Buttons benutzen" war die
    # einzige jemals moegliche Antwort, es gab keinen Ausweg.
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/setup"}})
    assert store.get_dialog("12345") is not None  # Dialog laeuft (Radtyp-Schritt)

    router.verarbeite_ein_update({"update_id": 2, "message": {"chat": {"id": 12345}, "text": "/help"}})

    assert "Gravel Deal Bot" in telegram.sent[-1][1]
    assert store.get_dialog("12345") is None  # Dialog wurde verworfen, nicht fortgesetzt


def test_profil_escapes_a_stuck_dialog_and_shows_profile(tmp_path):
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/setup"}})

    router.verarbeite_ein_update({"update_id": 2, "message": {"chat": {"id": 12345}, "text": "/profil"}})

    assert "Suchprofil" in telegram.sent[-1][1]
    assert store.get_dialog("12345") is None


def test_new_setup_mid_dialog_restarts_cleanly(tmp_path):
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/setup"}})
    # einen Radtyp per Button auswaehlen
    router.verarbeite_ein_update(
        {
            "update_id": 2,
            "callback_query": {
                "id": "cq1",
                "data": "radtyp:gravel",
                "message": {"chat": {"id": 12345}, "message_id": 1},
            },
        }
    )
    assert store.get_dialog("12345")["daten"]["radtypen"] == ["gravel"]

    router.verarbeite_ein_update({"update_id": 3, "message": {"chat": {"id": 12345}, "text": "/setup"}})

    dialog = store.get_dialog("12345")
    assert dialog is not None
    assert dialog["schritt"] == "radtyp"
    assert dialog["daten"]["radtypen"] == []  # frisch gestartet, nicht die alte Auswahl


def test_abbrechen_clears_a_running_dialog(tmp_path):
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/setup"}})
    assert store.get_dialog("12345") is not None

    router.verarbeite_ein_update({"update_id": 2, "message": {"chat": {"id": 12345}, "text": "/abbrechen"}})

    assert store.get_dialog("12345") is None
    assert "Abgebrochen" in telegram.sent[-1][1]


def test_abbrechen_without_active_dialog_is_harmless(tmp_path):
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/abbrechen"}})
    assert "Abgebrochen" in telegram.sent[-1][1]


def test_typing_weiter_at_radtyp_step_advances_like_the_button(tmp_path):
    # Genau das Szenario aus dem Bug-Report: der Nutzer tippt "Weiter" als
    # Text statt den Button anzutippen.
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/setup"}})
    router.verarbeite_ein_update(
        {
            "update_id": 2,
            "callback_query": {
                "id": "cq1",
                "data": "radtyp:gravel",
                "message": {"chat": {"id": 12345}, "message_id": 1},
            },
        }
    )

    router.verarbeite_ein_update({"update_id": 3, "message": {"chat": {"id": 12345}, "text": "Weiter"}})

    dialog = store.get_dialog("12345")
    assert dialog is not None
    assert dialog["schritt"] == "standort"  # naechster Schritt, nicht mehr radtyp


def test_typing_weiter_at_radtyp_step_without_selection_still_errors(tmp_path):
    router, telegram, store = _router(tmp_path)
    router.verarbeite_ein_update({"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/setup"}})

    router.verarbeite_ein_update({"update_id": 2, "message": {"chat": {"id": 12345}, "text": "weiter"}})

    assert "mindestens einen Radtyp" in telegram.sent[-1][1]
    dialog = store.get_dialog("12345")
    assert dialog is not None
    assert dialog["schritt"] == "radtyp"  # noch nicht weitergekommen
