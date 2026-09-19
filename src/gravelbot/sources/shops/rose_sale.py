"""Quelle: Rose Bikes Sale (Neuware mit Rabatt).

Struktur gegen echtes HTML von rosebikes.de/sale/fahrraeder verifiziert
(2026-09): jede Kachel ist ein ``catalog-product-tile`` mit
``data-test-abstract-sku``, der aktuelle Preis steht in
``.product-tile-price__current-value``, der Streichpreis (falls
reduziert) in ``.product-tile-price__old-value``. Kein JSON-LD auf der
Listenseite. Weitere Seiten kommen ueber den Chunk-Endpunkt
``/list/chunk/search?sf=1&category=<id>&page=<n>``, den die Seite selbst
per AJAX fuer "mehr laden" nutzt.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from gravelbot.config import HARD_EXCLUDE, ROSE_SALE_CATEGORY, Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis, attr_str, parse_price

log = logging.getLogger("gravel.sources.rose")

BASE = "https://www.rosebikes.de"
FIRST_PAGE_URL = BASE + "/sale/fahrr%C3%A4der?sf=1&category%5B%5D={category}"
CHUNK_URL = BASE + "/list/chunk/search?sf=1&category={category}&page={page}&chunk=2"


def parse_rose_sale_page(html_text: str) -> list[Listing]:
    soup = BeautifulSoup(html_text, "lxml")
    out: list[Listing] = []
    for tile in soup.select("catalog-product-tile[data-test-abstract-sku]"):
        anchor = tile.select_one("a.catalog-product-tile__link")
        if anchor is None:
            continue
        title = attr_str(anchor, "title").strip()
        if not title:
            continue
        low = title.lower()
        if any(w in low for w in HARD_EXCLUDE):
            continue
        href = attr_str(anchor, "href")
        current_el = tile.select_one(".product-tile-price__current-value")
        old_el = tile.select_one(".product-tile-price__old-value")
        price = parse_price(current_el.get_text(" ", strip=True)) if current_el else None
        list_price = parse_price(old_el.get_text(" ", strip=True)) if old_el else None
        if not price:
            continue
        out.append(
            Listing(
                source="rose_sale",
                source_id=attr_str(tile, "data-test-abstract-sku"),
                title=title,
                price_eur=price,
                url=href if href.startswith("http") else BASE + href,
                brand="Rose",
                seller_type="shop",
                shipping=True,
                is_new=True,
                list_price_eur=list_price,
            )
        )
    return out


class RoseSaleQuelle(QuelleBasis):
    name = "rose_sale"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def _fetch_kategorie(self, category: str, radtyp: str | None) -> list[Listing]:
        found: dict[str, Listing] = {}
        resp = self.http.get(FIRST_PAGE_URL.format(category=category))
        if resp is None:
            return []
        items = parse_rose_sale_page(resp.text)
        for item in items:
            item.radtyp = radtyp
            found.setdefault(item.key, item)
        for page in range(2, self.settings.shop_max_pages + 1):
            resp = self.http.get(CHUNK_URL.format(category=category, page=page))
            if resp is None:
                break
            items = parse_rose_sale_page(resp.text)
            if not items:
                break
            for item in items:
                item.radtyp = radtyp
                found.setdefault(item.key, item)
        return list(found.values())

    def suchen(self, profil: Profil) -> list[Listing]:
        found: dict[str, Listing] = {}
        gesehene: set[str] = set()
        for radtyp in profil.radtypen:
            category = ROSE_SALE_CATEGORY.get(radtyp)
            if not category or category in gesehene:
                continue
            gesehene.add(category)
            for item in self._fetch_kategorie(category, radtyp):
                found.setdefault(item.key, item)
        if not found:
            log.warning("Rose Sale: keine Treffer — Layout evtl. geaendert")
        return list(found.values())
