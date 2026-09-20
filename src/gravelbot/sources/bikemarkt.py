"""Quelle: Bikemarkt (MTB-News)."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from gravelbot.config import BIKEMARKT_CATEGORIES, Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis, attr_str, container_with_price, parse_price

log = logging.getLogger("gravel.sources.bikemarkt")

BASE = "https://bikemarkt.mtb-news.de"
ARTICLE_RE = re.compile(r"/article/(\d+)-")


def guess_condition(text: str) -> str | None:
    low = text.lower()
    for needle, label in [
        ("gebraucht, wie neu", "gebraucht, wie neu"),
        ("used, like new", "gebraucht, wie neu"),
        ("defekt", "defekt"),
        ("gebraucht", "gebraucht"),
        ("used", "gebraucht"),
        ("neu", "neu"),
        ("new", "neu"),
    ]:
        if needle in low:
            return label
    return None


def guess_brand(title: str) -> str | None:
    from gravelbot.config import BRANDS

    low = title.lower()
    for brand in sorted(BRANDS, key=len, reverse=True):
        if low.startswith(brand.lower()):
            return brand
    return None


def parse_bikemarkt_page(html_text: str, radtyp: str | None = None) -> list[Listing]:
    soup = BeautifulSoup(html_text, "lxml")
    out, seen = [], set()
    for anchor in soup.select('a[href*="/article/"]'):
        href = attr_str(anchor, "href")
        m = ARTICLE_RE.search(href)
        if not m or m.group(1) in seen:
            continue
        title = (attr_str(anchor, "title") or anchor.get_text(" ", strip=True) or "").strip()
        title = re.sub(r"\s+kaufen$", "", title).strip()
        if len(title) < 6:
            continue
        container = container_with_price(anchor)
        block = container.get_text(" ", strip=True)
        price = parse_price(block)
        if price is None:
            continue
        seen.add(m.group(1))
        out.append(
            Listing(
                source="bikemarkt",
                source_id=m.group(1),
                title=title,
                price_eur=price,
                url=(href if href.startswith("http") else BASE + href).split("?")[0],
                brand=guess_brand(title),
                condition=guess_condition(block),
                seller_type="shop" if ("Zum Shop" in str(container) or "Gewerblich" in block) else "private",
                radtyp=radtyp,
            )
        )
    return out


class BikemarktQuelle(QuelleBasis):
    name = "bikemarkt"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def suchen(self, profil: Profil) -> list[Listing]:
        found: dict[str, Listing] = {}
        for radtyp in profil.radtypen:
            for category in BIKEMARKT_CATEGORIES.get(radtyp, []):
                for page in range(1, self.settings.bikemarkt_max_pages + 1):
                    url = f"{BASE}/category/{category}-x?page={page}"
                    resp = self.http.get(url)
                    if resp is None:
                        break
                    items = parse_bikemarkt_page(resp.text, radtyp=radtyp)
                    if not items:
                        break
                    for item in items:
                        found.setdefault(item.key, item)
                    log.info("kat=%s seite=%s -> %s Inserate", category, page, len(items))
        return list(found.values())

    def volltext(self, query: str, max_seiten: int = 2) -> list[Listing]:
        """Nutzt die site-eigene Volltextsuche. Die Seite leitet
        ``/search?q_ft=X`` auf eine kanonische URL um (z.B. ``/search/Canyon``)
        — Pagination (``?page=N``) funktioniert nur auf dieser kanonischen
        URL, nicht auf der ursprünglichen ``q_ft``-URL (gegen die echte
        Seite verifiziert: ``?page=2`` auf der q_ft-URL liefert wieder Seite
        1). Deshalb erst die Umleitung abwarten und von der resultierenden
        URL aus weiterblättern.
        """
        found: dict[str, Listing] = {}
        resp = self.http.get(f"{BASE}/search?q_ft={quote(query)}")
        if resp is None:
            return []
        items = parse_bikemarkt_page(resp.text)
        for item in items:
            found.setdefault(item.key, item)
        if not items:
            return list(found.values())

        kanonische_url = resp.url
        for page in range(2, max_seiten + 1):
            resp = self.http.get(f"{kanonische_url}?page={page}")
            if resp is None:
                break
            items = parse_bikemarkt_page(resp.text)
            if not items:
                break
            for item in items:
                found.setdefault(item.key, item)
        return list(found.values())

    def details(self, listing: Listing) -> None:
        """Detailseite laden, um PLZ/Ort und Versandhinweis zu bekommen."""
        resp = self.http.get(listing.url)
        if resp is None:
            return
        text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
        listing.shipping = bool(
            re.search(r"versand (möglich|innerhalb|nach)", text, re.I)
            or re.search(r"shipping (possible|within)", text, re.I)
        )
        m = re.search(r"\b(\d{5})\s+([A-ZÄÖÜ][\wäöüß.\-]+(?:\s[A-ZÄÖÜ][\wäöüß.\-]+)?)", text)
        if m:
            listing.zip_code = m.group(1)
            listing.location = f"{m.group(1)} {m.group(2)}"
