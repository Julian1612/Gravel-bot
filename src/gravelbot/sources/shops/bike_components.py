"""Quelle: Bike-Components Komplettbikes im Sale.

Bike-Components ist vor allem ein Teile-Haendler; die allgemeine
Angebote-Seite (/de/angebote/angebote-gravel/) mischt reduzierte Teile
und Komplettbikes ohne verlaessliches Unterscheidungsmerkmal im HTML.
Deshalb wird stattdessen direkt die Komplettbike-Kategorie je Radtyp
abgefragt (z.B. /de/fahrraeder/rennraeder/gravelbike/) und dort nur die
Kacheln mit Sale-Kennzeichnung (Streichpreis) behalten — das schliesst
Teile automatisch aus, ohne sie erst erkennen zu muessen.

Struktur gegen echtes HTML verifiziert (2026-09): Kacheln sind
``a.js-product-item``, der Name steht in
``[data-test="auto-product-item-name"]``, der aktuelle Preis in
``[data-test="product-price"]``, der Streichpreis (UVP) in
``[data-test="product-strike-price"]``. Keine eigene Endurance-/
Cyclocross-Kategorie im Shop vorhanden — beides faellt auf "Rennrad".
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from gravelbot.config import BIKE_COMPONENTS_CATEGORY_PATH, HARD_EXCLUDE, Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis, attr_str, parse_price
from gravelbot.sources.bikemarkt import guess_brand

log = logging.getLogger("gravel.sources.bike_components")

BASE = "https://www.bike-components.de"


def parse_bike_components_page(html_text: str) -> list[Listing]:
    soup = BeautifulSoup(html_text, "lxml")
    out: list[Listing] = []
    for tile in soup.select("a.js-product-item"):
        strike_el = tile.select_one('[data-test="product-strike-price"]')
        if strike_el is None:
            continue  # kein Sale-Preis -> ueberspringen
        name_el = tile.select_one('[data-test="auto-product-item-name"]')
        price_el = tile.select_one('[data-test="product-price"]')
        title = (name_el.get_text(strip=True) if name_el else attr_str(tile, "title")).strip()
        if not title:
            continue
        if any(w in title.lower() for w in HARD_EXCLUDE):
            continue
        price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
        list_price = parse_price(strike_el.get_text(" ", strip=True))
        if not price:
            continue
        href = attr_str(tile, "href")
        product_id = attr_str(tile, "data-product-id") or href.rstrip("/").rsplit("-p", 1)[-1]
        out.append(
            Listing(
                source="bike_components",
                source_id=product_id,
                title=title,
                price_eur=price,
                url=href if href.startswith("http") else BASE + href,
                brand=guess_brand(title),
                seller_type="shop",
                shipping=True,
                is_new=True,
                list_price_eur=list_price,
            )
        )
    return out


class BikeComponentsQuelle(QuelleBasis):
    name = "bike_components"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def _fetch_kategorie(self, path: str, radtyp: str | None) -> list[Listing]:
        found: dict[str, Listing] = {}
        for page in range(1, self.settings.shop_max_pages + 1):
            suffix = "" if page == 1 else f"?page={page}"
            resp = self.http.get(f"{BASE}{path}{suffix}")
            if resp is None:
                break
            items = parse_bike_components_page(resp.text)
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
            path = BIKE_COMPONENTS_CATEGORY_PATH.get(radtyp)
            if not path or path in gesehene:
                continue
            gesehene.add(path)
            for item in self._fetch_kategorie(path, radtyp):
                found.setdefault(item.key, item)
        if not found:
            log.warning("Bike-Components: keine Treffer — Layout evtl. geaendert")
        return list(found.values())
