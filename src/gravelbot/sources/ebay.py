"""Quelle: eBay Browse API.

OAuth Client-Credentials-Flow. Der Token lebt nur zur Laufzeit dieses
Prozesses (Instanzattribut) — er kommt NIE in state.json, weil das Repo
oeffentlich ist. Da jeder GitHub-Actions-Lauf ein frischer Prozess ist,
wird ohnehin pro Lauf hoechstens einmal ein Token geholt; der Cache lohnt
sich vor allem bei lokalen Testlaeufen mit mehreren Aufrufen in einem
Prozess.

Doku: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
Lokale-Abholung-Filter (pickupCountry/pickupPostalCode/pickupRadius/
pickupRadiusUnit) sind dort offiziell dokumentiert und liefern nur
Inserate mit Abholoption in Reichweite — deshalb fragen wir zusaetzlich
per deliveryCountry:DE nach versandfaehigen Angeboten, damit wir wie bei
den anderen Quellen sowohl "lokal abholen" als auch "Versand" abdecken.
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from urllib.parse import quote

from gravelbot.config import EBAY_QUERY, Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import QuelleBasis, normalize_number

log = logging.getLogger("gravel.sources.ebay")

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"


@dataclass
class _TokenCache:
    token: str | None = None
    expires_at: float = 0.0


class EbayQuelle(QuelleBasis):
    name = "ebay"

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.settings = settings
        self._token_cache = _TokenCache()

    def aktiv(self) -> bool:
        return bool(self.settings.ebay_client_id and self.settings.ebay_client_secret)

    def inaktiv_grund(self) -> str | None:
        if not self.aktiv():
            return "EBAY_CLIENT_ID/EBAY_CLIENT_SECRET nicht gesetzt"
        return None

    def _token(self) -> str | None:
        now = time.time()
        if self._token_cache.token and now < self._token_cache.expires_at:
            return self._token_cache.token
        creds = base64.b64encode(
            f"{self.settings.ebay_client_id}:{self.settings.ebay_client_secret}".encode()
        ).decode()
        resp = self.http.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": OAUTH_SCOPE},
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if resp is None or resp.status_code != 200:
            log.warning("eBay-Token nicht erhalten (%s)", getattr(resp, "status_code", "?"))
            return None
        data = resp.json()
        token = data.get("access_token")
        if not token:
            return None
        self._token_cache.token = token
        self._token_cache.expires_at = now + float(data.get("expires_in", 7200)) - 60
        return token

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.settings.ebay_marketplace_id,
            "Content-Type": "application/json",
        }

    def _search_raw(self, query: str, filter_str: str, limit: int) -> list[dict]:
        token = self._token()
        if not token:
            return []
        params = (
            f"q={quote(query)}&category_ids={self.settings.ebay_category_id}"
            f"&filter={quote(filter_str, safe=':,[]')}&limit={limit}"
        )
        resp = self.http.get(f"{SEARCH_URL}?{params}", headers=self._headers(token))
        if resp is None or resp.status_code != 200:
            log.warning("eBay-Suche fehlgeschlagen (%s) fuer %r", getattr(resp, "status_code", "?"), query)
            return []
        return list(resp.json().get("itemSummaries") or [])

    def _map_item(self, item: dict, radtyp: str | None) -> Listing | None:
        price = item.get("price") or {}
        value = normalize_number(str(price.get("value", "")))
        title = item.get("title")
        url = item.get("itemWebUrl")
        item_id = item.get("itemId")
        if not (value and title and url and item_id):
            return None
        loc = item.get("itemLocation") or {}
        location_bits = [loc.get("postalCode"), loc.get("city")]
        location = " ".join(str(b) for b in location_bits if b) or None
        from gravelbot.sources.bikemarkt import guess_brand

        seller = item.get("seller") or {}
        account_type = seller.get("sellerAccountType", "").upper()
        seller_type = "private" if account_type == "INDIVIDUAL" else "shop"

        return Listing(
            source="ebay",
            source_id=item_id,
            title=title,
            price_eur=value,
            url=url,
            brand=guess_brand(title),
            condition=item.get("condition"),
            seller_type=seller_type,
            seller_name=seller.get("username"),
            location=location,
            zip_code=loc.get("postalCode"),
            shipping=bool(item.get("shippingOptions")),
            radtyp=radtyp,
        )

    def _search_query(self, query: str, profil: Profil, radtyp: str | None) -> list[Listing]:
        price_filter = f"price:[{int(profil.min_price_eur)}..{int(profil.max_price_eur)}],priceCurrency:EUR"
        raw: dict[str, dict] = {}

        if profil.include_shipping_offers:
            for item in self._search_raw(query, f"{price_filter},deliveryCountry:DE", limit=50):
                raw.setdefault(item.get("itemId", ""), item)

        if profil.home_plz:
            pickup_filter = (
                f"{price_filter},pickupCountry:DE,pickupPostalCode:{profil.home_plz},"
                f"pickupRadius:{int(profil.max_distance_km)},pickupRadiusUnit:km"
            )
            for item in self._search_raw(query, pickup_filter, limit=50):
                raw.setdefault(item.get("itemId", ""), item)

        listings = []
        for item in raw.values():
            mapped = self._map_item(item, radtyp)
            if mapped:
                listings.append(mapped)
        return listings

    def suchen(self, profil: Profil) -> list[Listing]:
        found: dict[str, Listing] = {}
        for radtyp in profil.radtypen:
            query = EBAY_QUERY.get(radtyp, radtyp)
            for item in self._search_query(query, profil, radtyp):
                found.setdefault(item.key, item)
        return list(found.values())

    def volltext(self, query: str, max_seiten: int = 2) -> list[Listing]:
        token = self._token()
        if not token:
            return []
        items = self._search_raw(query, "priceCurrency:EUR", limit=50)
        out = []
        for item in items:
            mapped = self._map_item(item, radtyp=None)
            if mapped:
                out.append(mapped)
        return out
