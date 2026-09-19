"""Quelle: Bike-Discount Sale/B-Ware — DEAKTIVIERT.

Sowohl /de/sale als auch die B-Ware-Uebersicht antworten mit HTTP 403 —
und zwar unabhaengig vom User-Agent (getestet mit einem normalen
Browser-UA UND mit unserem ehrlichen Bot-UA, beide 403, auch nach
Redirects). Das sieht nach serverseitigem Bot-Schutz (Cloudflare/Akamai-
artig) aus, nicht nach einem einfachen UA-Filter. Wir haben keine
Selektoren gegen echtes HTML pruefen koennen und bauen deshalb keinen
Parser auf Verdacht — die Quelle bleibt bewusst deaktiviert, bis sich das
aendert oder eine offizielle API auftaucht.
"""

from __future__ import annotations

from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis


class BikeDiscountQuelle(QuelleBasis):
    name = "bike_discount"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def aktiv(self) -> bool:
        return False

    def inaktiv_grund(self) -> str | None:
        return "Shop liefert HTTP 403 fuer alle getesteten User-Agents (Bot-Schutz)"

    def suchen(self, profil: Profil) -> list[Listing]:
        return []
