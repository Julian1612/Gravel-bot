from __future__ import annotations

from gravelbot.http import _retry_after_seconds


def test_retry_after_seconds_parses_plain_integer():
    assert _retry_after_seconds("5", fallback=99) == 5


def test_retry_after_seconds_falls_back_on_missing_header():
    assert _retry_after_seconds(None, fallback=7) == 7


def test_retry_after_seconds_falls_back_on_http_date_form():
    # RFC 7231 erlaubt neben Ganzzahl-Sekunden auch ein HTTP-Datum wie
    # "Wed, 21 Oct 2026 07:28:00 GMT" — ein blankes int() darauf wuerde mit
    # ValueError abstuerzen.
    assert _retry_after_seconds("Wed, 21 Oct 2026 07:28:00 GMT", fallback=12) == 12
