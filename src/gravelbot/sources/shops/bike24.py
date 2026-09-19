"""Quelle: Bike24 Sale — DEAKTIVIERT.

Gleicher Befund wie bei Bike-Discount: HTTP 403 fuer die Sale-Uebersicht,
sowohl mit Browser-UA als auch mit unserem ehrlichen Bot-UA. Ohne
Einblick in echtes HTML bauen wir keinen Parser — Quelle bleibt bewusst
deaktiviert und geloggt, bis sich der Zugriff aendert.
"""

from __future__ import annotations

from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis


class Bike24Quelle(QuelleBasis):
    name = "bike24"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def aktiv(self) -> bool:
        return False

    def inaktiv_grund(self) -> str | None:
        return "Shop liefert HTTP 403 fuer alle getesteten User-Agents (Bot-Schutz)"

    def suchen(self, profil: Profil) -> list[Listing]:
        return []
