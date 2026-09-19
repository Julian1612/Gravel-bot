from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gravelbot.app import _ist_digest_zeit

BERLIN = ZoneInfo("Europe/Berlin")


def test_ist_digest_zeit_trifft_innerhalb_fenster():
    jetzt = datetime(2026, 9, 19, 8, 10, tzinfo=BERLIN)
    assert _ist_digest_zeit(["08:00", "19:00"], jetzt) is True


def test_ist_digest_zeit_verpasst_ausserhalb_fenster():
    jetzt = datetime(2026, 9, 19, 12, 0, tzinfo=BERLIN)
    assert _ist_digest_zeit(["08:00", "19:00"], jetzt) is False


def test_ist_digest_zeit_ignoriert_kaputte_eintraege():
    jetzt = datetime(2026, 9, 19, 8, 5, tzinfo=BERLIN)
    assert _ist_digest_zeit(["nicht-valide", "08:00"], jetzt) is True
