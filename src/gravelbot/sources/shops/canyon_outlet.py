"""Quelle: Canyon Fahrrad-Outlet (Neuware mit Rabatt).

Struktur gegen echtes HTML von canyon.com/de-de/fahrrad-outlet/ verifiziert
(2026-09): jede Produktkachel ist ein ``div[data-pid]`` mit einem
``data-gtm-impression``-Attribut, das ein JSON-Array mit den Feldern
item_name, item_id, item_brand, item_category2 (z.B. "Gravel Outlet"),
price (Aktionspreis) und gross_price (UVP) enthaelt — genau der
Streichpreis, den wir fuer den Rabattwert brauchen. Kein JSON-LD auf der
Listenseite, daher direkt dieses eingebettete JSON statt HTML-Fallback.
"""

from __future__ import annotations

import html
import json
import logging

from bs4 import BeautifulSoup

from gravelbot.config import CANYON_CATEGORY, HARD_EXCLUDE, Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis, attr_str

log = logging.getLogger("gravel.sources.canyon")

LIST_URL = "https://www.canyon.com/de-de/fahrrad-outlet/?searchType=bikes&start={start}&sz={sz}"
PAGE_SIZE = 48


def parse_canyon_outlet_page(html_text: str, kategorie: str | None = None) -> list[Listing]:
    soup = BeautifulSoup(html_text, "lxml")
    out: list[Listing] = []
    for tile in soup.select("div[data-pid]"):
        raw = attr_str(tile, "data-gtm-impression")
        if not raw:
            continue
        try:
            impressions = json.loads(html.unescape(raw))
            item = impressions[0]["ecommerce"]["items"][0]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            continue
        item_category2 = item.get("item_category2", "")
        if kategorie and item_category2 != kategorie:
            continue
        name = str(item.get("item_name", "")).strip()
        if not name or len(name) < 3:
            continue
        low = name.lower()
        if any(w in low for w in HARD_EXCLUDE):
            continue
        price = item.get("price")
        gross_price = item.get("gross_price")
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        link = tile.select_one("a[href]")
        url = attr_str(link, "href")
        if not url:
            continue
        out.append(
            Listing(
                source="canyon_outlet",
                source_id=str(item.get("item_id") or attr_str(tile, "data-pid")),
                title=name,
                price_eur=float(price),
                url=url.split("?")[0],
                brand=item.get("item_brand") or "Canyon",
                seller_type="shop",
                shipping=True,
                is_new=True,
                list_price_eur=float(gross_price) if isinstance(gross_price, (int, float)) else None,
            )
        )
    return out


class CanyonOutletQuelle(QuelleBasis):
    name = "canyon_outlet"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def _fetch_kategorie(self, kategorie: str, radtyp: str | None) -> list[Listing]:
        found: dict[str, Listing] = {}
        for page in range(self.settings.shop_max_pages):
            start = page * PAGE_SIZE
            resp = self.http.get(LIST_URL.format(start=start, sz=PAGE_SIZE))
            if resp is None:
                break
            items = parse_canyon_outlet_page(resp.text, kategorie=kategorie)
            if not items:
                break
            for item in items:
                item.radtyp = radtyp
                found.setdefault(item.key, item)
            if len(items) < PAGE_SIZE:
                break
        return list(found.values())

    def suchen(self, profil: Profil) -> list[Listing]:
        found: dict[str, Listing] = {}
        gesehene_kategorien: set[str] = set()
        for radtyp in profil.radtypen:
            kategorie = CANYON_CATEGORY.get(radtyp)
            if not kategorie or kategorie in gesehene_kategorien:
                continue
            gesehene_kategorien.add(kategorie)
            for item in self._fetch_kategorie(kategorie, radtyp):
                found.setdefault(item.key, item)
        if not found:
            log.warning("Canyon Outlet: keine Treffer — Layout evtl. geaendert")
        return list(found.values())
