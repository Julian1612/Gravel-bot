"""Quelle: Focus-Bikes Outlet — DEAKTIVIERT.

focus-bikes.com/int/de-de/outlet liefert server-seitig nur das
Storyblok-CMS-Geruest (window.__STORYBLOK_STATE__, keine "€"-Zeichen, keine
Produktkacheln im HTML) — die Outlet-Liste wird erst clientseitig per JS
nachgeladen. Gleicher Befund wie bei radon-bikes.de/outlet/: ohne
Headless-Browser kein echtes HTML zum Verifizieren einer Struktur — Quelle
bleibt bewusst deaktiviert und geloggt, bis sich die Seite aendert.
"""

from __future__ import annotations

from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis


class FocusOutletQuelle(QuelleBasis):
    name = "focus_outlet"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def aktiv(self) -> bool:
        return False

    def inaktiv_grund(self) -> str | None:
        return (
            "Outlet-Seite ist eine JS-SPA ohne Produktdaten im Server-HTML (kein Headless-Browser im Einsatz)"
        )

    def suchen(self, profil: Profil) -> list[Listing]:
        return []
