"""Quelle: Radon-Bikes Outlet — DEAKTIVIERT.

radon-bikes.de/outlet/ liefert nur ein leeres Next.js-App-Router-Geruest
(server-seitig kein einziges Produkt, kein Preis, keine "€" im HTML) —
die Produktdaten werden erst nach dem Laden per clientseitigem JavaScript
nachgeladen. Ohne Headless-Browser (den dieses Projekt bewusst nicht
einsetzt, siehe README) gibt es kein echtes HTML zum Verifizieren einer
Struktur — Quelle bleibt bewusst deaktiviert und geloggt, bis sich die
Seite aendert oder eine oeffentliche API dafuer gefunden wird.
"""

from __future__ import annotations

from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis


class RadonOutletQuelle(QuelleBasis):
    name = "radon_outlet"

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
