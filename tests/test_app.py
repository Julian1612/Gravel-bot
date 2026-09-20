from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gravelbot.app import TELEGRAM_MAX_MESSAGE_CHARS, _chunk_by_length, _ist_digest_zeit, _scan_und_melden
from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.storage.store import Store

BERLIN = ZoneInfo("Europe/Berlin")


class _FakeTelegram:
    enabled = False

    def __init__(self):
        self.sent: list[str] = []

    def send(self, text, chat_id=None, preview=True, keyboard=None):
        self.sent.append(text)
        return 1


class _FakeQuelle:
    name = "fake"

    def __init__(self, listings: list[Listing]):
        self._listings = listings

    def aktiv(self) -> bool:
        return True

    def inaktiv_grund(self):
        return None

    def suchen(self, profil: Profil) -> list[Listing]:
        return self._listings

    def details(self, listing: Listing) -> None:
        return None


def test_ist_digest_zeit_trifft_innerhalb_fenster():
    jetzt = datetime(2026, 9, 19, 8, 10, tzinfo=BERLIN)
    assert _ist_digest_zeit(["08:00", "19:00"], jetzt) is True


def test_ist_digest_zeit_verpasst_ausserhalb_fenster():
    jetzt = datetime(2026, 9, 19, 12, 0, tzinfo=BERLIN)
    assert _ist_digest_zeit(["08:00", "19:00"], jetzt) is False


def test_ist_digest_zeit_ignoriert_kaputte_eintraege():
    jetzt = datetime(2026, 9, 19, 8, 5, tzinfo=BERLIN)
    assert _ist_digest_zeit(["nicht-valide", "08:00"], jetzt) is True


def test_chunk_by_length_keeps_short_texts_in_one_message():
    texte = ["a" * 100, "b" * 100, "c" * 100]
    chunks = _chunk_by_length(texte, "\n\n", 1000)
    assert chunks == ["\n\n".join(texte)]


def test_chunk_by_length_splits_before_exceeding_limit():
    # Regression: 20 volle Deal-Texte in EINER Nachricht koennen leicht
    # Telegrams 4096-Zeichen-Limit sprengen und die ganze Nachricht faellt
    # durch, statt nur gekuerzt zu werden.
    texte = ["x" * 2000 for _ in range(3)]
    chunks = _chunk_by_length(texte, "\n\n", TELEGRAM_MAX_MESSAGE_CHARS)
    assert len(chunks) == 3
    assert all(len(c) <= TELEGRAM_MAX_MESSAGE_CHARS for c in chunks)


def test_chunk_by_length_never_produces_empty_chunks_for_nonempty_input():
    texte = [f"deal {i}" for i in range(50)]
    chunks = _chunk_by_length(texte, "\n\n", 50)
    assert all(chunks)
    assert "\n\n".join(chunks).count("deal ") == 50


def test_chunk_by_length_of_empty_list_is_empty():
    assert _chunk_by_length([], "\n\n", 1000) == []


def test_scan_und_melden_skips_listings_from_blocked_sellers(tmp_path):
    # Regression: is_seller_blocked() existierte im Store, wurde aber nie im
    # eigentlichen Scan-Filter abgefragt — geblockte Verkaeufer wurden trotz
    # Blockliste weiter gemeldet.
    settings = Settings()
    store = Store(str(tmp_path / "state.json"))
    store.block_seller("boeser_verkaeufer")

    listing = Listing(
        source="ebay",
        source_id="1",
        title="Canyon Grizl CF SL 8",
        price_eur=2000,
        url="https://example.test/1",
        seller_name="boeser_verkaeufer",
    )
    quelle = _FakeQuelle([listing])
    http = Http(settings)
    telegram = _FakeTelegram()

    _scan_und_melden(store, settings, http, telegram, [quelle], {"ebay": quelle}, dry_run=False)

    assert store.get(listing.key) is None
