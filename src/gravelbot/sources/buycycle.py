"""Quelle: buycycle."""

from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from gravelbot.config import BUYCYCLE_QUERY, Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis, attr_str, normalize_number, parse_price, walk

log = logging.getLogger("gravel.sources.buycycle")

BASE = "https://buycycle.com"
BIKE_RE = re.compile(r"/bike/(?:[\w-]*?-)?(\d+)\b")


def parse_buycycle_page(html_text: str, radtyp: str | None = None) -> list[Listing]:
    soup = BeautifulSoup(html_text, "lxml")
    out: dict[str, Listing] = {}

    # 1) JSON-LD
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in walk(data):
            if node.get("@type") != "Product":
                continue
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = normalize_number(str(offers.get("price", node.get("price", ""))))
            url, name = node.get("url", ""), node.get("name", "")
            if not (price and url and name):
                continue
            m = BIKE_RE.search(url)
            sid = m.group(1) if m else url.rstrip("/").rsplit("/", 1)[-1]
            brand = node.get("brand")
            brand = brand.get("name") if isinstance(brand, dict) else brand
            item = Listing(
                "buycycle",
                sid,
                name.strip(),
                price,
                url if url.startswith("http") else BASE + url,
                brand=brand if isinstance(brand, str) else None,
                seller_type="marketplace",
                shipping=True,
                radtyp=radtyp,
            )
            out.setdefault(item.key, item)
    if out:
        return list(out.values())

    # 2) Eingebettetes Next.js-JSON
    next_data_script = soup.select_one("script#__NEXT_DATA__")
    if next_data_script and next_data_script.string:
        try:
            data = json.loads(next_data_script.string)
        except json.JSONDecodeError:
            data = None
        for node in walk(data or {}):
            if not {"id", "price"} <= set(node):
                continue
            title = (
                node.get("name")
                or node.get("title")
                or " ".join(str(node.get(k, "")) for k in ("brand", "family", "model")).strip()
            )
            price = normalize_number(str(node.get("price")))
            if not title or not price:
                continue
            slug = node.get("slug") or node.get("id")
            item = Listing(
                "buycycle",
                node["id"],
                title,
                price,
                f"{BASE}/de-de/bike/{slug}",
                brand=node.get("brand") if isinstance(node.get("brand"), str) else None,
                seller_type="marketplace",
                shipping=True,
                radtyp=radtyp,
            )
            out.setdefault(item.key, item)
    if out:
        return list(out.values())

    # 3) Stumpfes HTML
    for anchor in soup.select('a[href*="/bike/"]'):
        href = attr_str(anchor, "href")
        m = BIKE_RE.search(href)
        if not m:
            continue
        node, block = anchor, ""
        for _ in range(4):
            block = node.get_text(" ", strip=True)
            if "€" in block or node.parent is None:
                break
            node = node.parent
        price = parse_price(block)
        title = (attr_str(anchor, "title") or anchor.get_text(" ", strip=True)).strip()
        if not price or len(title) < 6:
            continue
        item = Listing(
            "buycycle",
            m.group(1),
            title,
            price,
            href if href.startswith("http") else BASE + href,
            seller_type="marketplace",
            shipping=True,
            radtyp=radtyp,
        )
        out.setdefault(item.key, item)
    return list(out.values())


class BuycycleQuelle(QuelleBasis):
    name = "buycycle"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def _suchen_query(self, query: str, max_seiten: int, radtyp: str | None) -> list[Listing]:
        found: dict[str, Listing] = {}
        for page in range(1, max_seiten + 1):
            resp = self.http.get(f"{BASE}/de-de/shop?query={query}&page={page}")
            if resp is None:
                break
            items = parse_buycycle_page(resp.text, radtyp=radtyp)
            if not items:
                log.warning("Seite %s ohne Treffer (query=%s)", page, query)
                break
            for item in items:
                found.setdefault(item.key, item)
            log.info("query=%s seite=%s -> %s Inserate", query, page, len(items))
        return list(found.values())

    def suchen(self, profil: Profil) -> list[Listing]:
        found: dict[str, Listing] = {}
        for radtyp in profil.radtypen:
            query = BUYCYCLE_QUERY.get(radtyp, radtyp)
            for item in self._suchen_query(query, self.settings.buycycle_max_pages, radtyp):
                found.setdefault(item.key, item)
        return list(found.values())

    def volltext(self, query: str, max_seiten: int = 2) -> list[Listing]:
        return self._suchen_query(query, max_seiten, radtyp=None)
