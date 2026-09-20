"""Quelle: fahrrad.de (Neuware, Shopify-Shop).

Kein HTML-Scraping noetig: Shopify-Shops liefern jede Kollektion auch als
oeffentliches JSON unter ``/collections/<slug>/products.json`` (verifiziert
gegen echte Responses von fahrrad.de, 2026-09) — strukturierter und
stabiler als HTML-Selektoren. Jede Groesse ist eine eigene "variant" mit
eigenem Preis/Streichpreis/Verfuegbarkeit; wir bilden daraus eine eigene
Listing pro verfuegbarer Groesse, damit der Rahmengroessen-Filter im
Profil (Profil.frame_sizes) direkt greift statt nur auf die guenstigste
Groesse eines Produkts zu schauen.

Die Kollektionen ("gravel-bikes" etc., siehe config.FAHRRAD_DE_COLLECTION)
enthalten trotz Namen auch Nicht-Komplettbikes (z.B. Kinder-Gravelbikes) —
deshalb zusaetzlich ein product_type-Whitelist-Filter.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from gravelbot.config import FAHRRAD_DE_COLLECTION, FAHRRAD_DE_PRODUCT_TYPES, HARD_EXCLUDE, Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis

log = logging.getLogger("gravel.sources.fahrrad_de")

BASE = "https://www.fahrrad.de"
COLLECTION_URL = BASE + "/collections/{slug}/products.json?limit={limit}&page={page}"
PAGE_SIZE = 250

_GROESSE_PRAEFIX_RE = re.compile(r"(?i)^h\s*")
_GROESSE_CM_SUFFIX_RE = re.compile(r"(?i)\s*cm$")


def _normalisiere_groesse(variant_title: str) -> str | None:
    """'H 46cm' -> '46', '50cm' -> '50', 'xs' -> 'XS', '56' -> '56'."""
    wert = _GROESSE_PRAEFIX_RE.sub("", (variant_title or "").strip())
    wert = _GROESSE_CM_SUFFIX_RE.sub("", wert).strip()
    if not wert:
        return None
    return wert.upper() if wert.isalpha() else wert


@dataclass
class FahrradDeSeite:
    listings: list[Listing]
    ist_letzte_seite: bool


def parse_fahrrad_de_collection(json_text: str) -> FahrradDeSeite:
    """Eine Listing pro verfuegbarer Groesse (Variante). ``ist_letzte_seite``
    zeigt an, ob die Rohantwort weniger Produkte als PAGE_SIZE enthielt —
    das Signal fuer den Aufrufer, die Pagination zu stoppen."""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return FahrradDeSeite([], True)
    products = data.get("products") or []
    out: list[Listing] = []
    for product in products:
        product_type = product.get("product_type") or ""
        if product_type not in FAHRRAD_DE_PRODUCT_TYPES:
            continue
        title = str(product.get("title") or "").strip()
        if not title:
            continue
        low = title.lower()
        if any(w in low for w in HARD_EXCLUDE):
            continue
        handle = product.get("handle") or ""
        brand = product.get("vendor") or None
        for variant in product.get("variants") or []:
            if not variant.get("available"):
                continue
            price = variant.get("price")
            try:
                price_eur = float(price)
            except (TypeError, ValueError):
                continue
            if price_eur <= 0:
                continue
            compare_at = variant.get("compare_at_price")
            try:
                list_price_eur = float(compare_at) if compare_at else None
            except (TypeError, ValueError):
                list_price_eur = None
            listing = Listing(
                source="fahrrad_de",
                source_id=f"{product.get('id')}-{variant.get('id')}",
                title=title,
                price_eur=price_eur,
                url=f"{BASE}/products/{handle}?variant={variant.get('id')}",
                brand=brand,
                seller_type="shop",
                shipping=True,
                is_new=True,
                list_price_eur=list_price_eur,
                frame_size=_normalisiere_groesse(str(variant.get("title") or "")),
            )
            out.append(listing)
    return FahrradDeSeite(out, len(products) < PAGE_SIZE)


class FahrradDeQuelle(QuelleBasis):
    name = "fahrrad_de"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings

    def _fetch_kollektion(self, slug: str, radtyp: str | None) -> list[Listing]:
        found: dict[str, Listing] = {}
        for page in range(1, self.settings.shop_max_pages + 1):
            url = COLLECTION_URL.format(slug=slug, limit=PAGE_SIZE, page=page)
            resp = self.http.get(url)
            if resp is None:
                break
            seite = parse_fahrrad_de_collection(resp.text)
            for listing in seite.listings:
                listing.radtyp = radtyp
                found.setdefault(listing.key, listing)
            if seite.ist_letzte_seite:
                break
        return list(found.values())

    def suchen(self, profil: Profil) -> list[Listing]:
        found: dict[str, Listing] = {}
        gesehene_slugs: set[str] = set()
        for radtyp in profil.radtypen:
            slug = FAHRRAD_DE_COLLECTION.get(radtyp)
            if not slug or slug in gesehene_slugs:
                continue
            gesehene_slugs.add(slug)
            for item in self._fetch_kollektion(slug, radtyp):
                found.setdefault(item.key, item)
        if not found:
            log.warning("fahrrad.de: keine Treffer — Shopify-API evtl. geaendert")
        return list(found.values())
