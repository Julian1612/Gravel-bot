from __future__ import annotations

from gravelbot.models import Listing, Profil
from gravelbot.sources.registry import durchsuche_alle, volltextsuche_alle


class _KaputteQuelle:
    name = "kaputt"

    def aktiv(self) -> bool:
        return True

    def inaktiv_grund(self):
        return None

    def suchen(self, profil: Profil) -> list[Listing]:
        raise RuntimeError("Layout hat sich geaendert")

    def volltext(self, query: str, max_seiten: int = 2) -> list[Listing]:
        raise RuntimeError("kaputt")


class _FunktionierendeQuelle:
    name = "gut"

    def aktiv(self) -> bool:
        return True

    def inaktiv_grund(self):
        return None

    def suchen(self, profil: Profil) -> list[Listing]:
        return [Listing("gut", "1", "Canyon Grizl", 1500, "https://example.test/1")]

    def volltext(self, query: str, max_seiten: int = 2) -> list[Listing]:
        return [Listing("gut", "1", "Canyon Grizl", 1500, "https://example.test/1")]


class _InaktiveQuelle:
    name = "inaktiv"

    def aktiv(self) -> bool:
        return False

    def inaktiv_grund(self):
        return "Credentials fehlen"

    def suchen(self, profil: Profil) -> list[Listing]:
        raise AssertionError("darf bei inaktiver Quelle nicht aufgerufen werden")


def test_durchsuche_alle_isoliert_fehlerhafte_quelle():
    listings, berichte = durchsuche_alle(
        [_KaputteQuelle(), _FunktionierendeQuelle(), _InaktiveQuelle()], Profil()
    )
    assert len(listings) == 1
    assert listings[0].source == "gut"

    by_name = {b.name: b for b in berichte}
    assert by_name["kaputt"].fehler is not None
    assert by_name["gut"].fehler is None
    assert by_name["gut"].treffer == 1
    assert by_name["inaktiv"].aktiv is False
    assert by_name["inaktiv"].grund == "Credentials fehlen"


def test_volltextsuche_alle_ignoriert_fehlerhafte_quelle_und_dedupliziert():
    ergebnis = volltextsuche_alle(
        [_KaputteQuelle(), _FunktionierendeQuelle()], "grizl", max_seiten=2, gesamtlimit=10
    )
    assert len(ergebnis) == 1
    assert ergebnis[0].key == "gut:1"


def test_volltextsuche_alle_respektiert_gesamtlimit():
    quelle = _FunktionierendeQuelle()
    ergebnis = volltextsuche_alle([quelle], "grizl", max_seiten=2, gesamtlimit=0)
    assert ergebnis == []
