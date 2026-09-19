#!/usr/bin/env python3
"""
Gravel Deal Bot — alles in einer Datei.

Sucht auf Bikemarkt (MTB-News) und buycycle nach Gravelbikes, merkt sich
Preise, erkennt Schnaeppchen und schickt sie per Telegram.

Laeuft als GitHub Action. Einstellungen: direkt hier unten im Block EINSTELLUNGEN.
Test ohne Senden:  python bot.py --dry-run
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import math
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ════════════════════════════════════════════════════════════════════════════
#  EINSTELLUNGEN — nur hier musst du etwas aendern
# ════════════════════════════════════════════════════════════════════════════

# Dein Standort (Stuttgart) und wie weit du fahren wuerdest
HOME_LAT = 48.7758
HOME_LON = 9.1829
MAX_DISTANCE_KM = 200

# Inserate ohne erkennbaren Standort trotzdem melden?
INCLUDE_UNKNOWN_LOCATION = True
# Angebote mit Versand auch dann, wenn sie weiter weg sind?
INCLUDE_SHIPPING_OFFERS = True

# Preisrahmen
MIN_PRICE_EUR = 500
MAX_PRICE_EUR = 3500

# Titel mit diesen Woertern werden ignoriert
EXCLUDE_KEYWORDS = [
    "rahmenset", "frameset", "e-bike", "pedelec", "kinder",
    "gesucht", "suche", "tausch gegen",
]
# Nur Inserate mit einem dieser Woerter ([] = alle durchlassen)
INCLUDE_KEYWORDS: list[str] = []
# Nur diese Rahmengroessen, z.B. ["56", "58", "L"]  ([] = alle)
FRAME_SIZES: list[str] = []

# Wann ist es ein Deal?
MIN_DISCOUNT_PCT = 15       # Prozent unter dem Median vergleichbarer Inserate
MIN_PRICE_DROP_PCT = 7      # Prozent Preissenkung seit dem letzten Lauf
MIN_SAMPLES_FOR_MEDIAN = 4  # ab so vielen Vergleichspreisen zaehlt der Median
MAX_ALERTS_PER_RUN = 12     # Deckel gegen Telegram-Fluten
SEED_RUN_SILENT = True      # erster Lauf sammelt nur, sendet nicht

# Quellen
BIKEMARKT_ENABLED = True
BIKEMARKT_CATEGORIES = [123]   # 123 = Gravel Bike, 194 = Rennrad & Gravel
BIKEMARKT_MAX_PAGES = 6
BUYCYCLE_ENABLED = True
BUYCYCLE_MAX_PAGES = 3

# Hoeflichkeit beim Abrufen
USER_AGENT = "gravel-deal-bot/1.0 (persoenlicher Preisalarm)"
REQUEST_DELAY_SECONDS = 1.2
TIMEOUT_SECONDS = 20
MAX_RETRIES = 3

STATE_FILE = "state.json"

# ════════════════════════════════════════════════════════════════════════════
#  Ab hier musst du nichts mehr anfassen
# ════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gravel")

BIKEMARKT_BASE = "https://bikemarkt.mtb-news.de"
BUYCYCLE_BASE = "https://buycycle.com"
ARTICLE_RE = re.compile(r"/article/(\d+)-")
BIKE_RE = re.compile(r"/bike/(?:[\w-]*?-)?(\d+)\b")
PRICE_RE = re.compile(r"(?:€\s*([\d.,]+)|([\d.,]+)\s*(?:€|EUR))")
ZIP_RE = re.compile(r"\b(\d{5})\b")

BRANDS = [
    "Rose Bikes", "NS Bikes", "Marin Bikes", "Basic Bikes", "Crossworx Bikes",
    "Dinolfo Cycles", "J.Guillem", "VanNicholas", "Van Nicholas", "Cannondale",
    "Specialized", "Bergamont", "Nukeproof", "Propain", "Cervélo", "Cervelo",
    "Santa Cruz", "Rocky Mountain", "Canyon", "Merida", "Giant", "Orbea",
    "Ridley", "Rondo", "Scott", "Trek", "Cube", "Kona", "Koga", "Niner",
    "Focus", "Stevens", "Storck", "Genesis", "Salsa", "Surly", "Open",
    "Ibis", "Norco", "Fuji", "Lapierre", "BMC", "Bianchi", "Wilier", "3T",
]

MODEL_NOISE = {
    "gravel", "gravelbike", "bike", "rad", "carbon", "alu", "aluminium",
    "neu", "neuwertig", "gebraucht", "gr", "rh", "größe", "groesse",
    "wie", "top", "zustand", "cm", "de", "the", "mit", "und",
}


# ── Kleinkram ───────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_number(raw: str) -> float | None:
    """'1.690' / '1,690' / '2.299,98' / '2,299.98' -> float"""
    raw = (raw or "").strip().rstrip(".,")
    if not raw or not any(c.isdigit() for c in raw):
        return None
    has_dot, has_comma = "." in raw, "," in raw
    if has_dot and has_comma:
        dec = "." if raw.rfind(".") > raw.rfind(",") else ","
        thou = "," if dec == "." else "."
        raw = raw.replace(thou, "").replace(dec, ".")
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        tail = raw.rsplit(sep, 1)[1]
        raw = raw.replace(sep, "." if len(tail) == 2 else "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_price(text: str) -> float | None:
    for m in PRICE_RE.finditer(text or ""):
        value = normalize_number(m.group(1) or m.group(2) or "")
        if value and 20 <= value <= 30000:
            return value
    return None


def fmt_eur(value: float) -> str:
    return f"{value:,.0f} €".replace(",", ".")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ── Inserat ─────────────────────────────────────────────────────────────────

class Listing:
    def __init__(self, source, source_id, title, price_eur, url, brand=None,
                 condition=None, seller_type=None, location=None, shipping=False):
        self.source = source
        self.source_id = str(source_id)
        self.title = title
        self.price_eur = price_eur
        self.url = url
        self.brand = brand
        self.condition = condition
        self.seller_type = seller_type
        self.location = location
        self.shipping = shipping
        self.zip_code: str | None = None
        self.distance_km: float | None = None

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def model_key(self) -> str:
        """Bucket fuer den Median: 'Canyon Grizl CF SL 8 AXS' -> 'canyon grizl'"""
        title = re.sub(r"[^a-z0-9äöüß\s]", " ", self.title.lower())
        tokens = [t for t in title.split() if t]
        brand = (self.brand or "").lower().strip()
        if brand:
            bt = brand.split()
            if tokens[:len(bt)] == bt:
                tokens = tokens[len(bt):]
        else:
            brand = tokens[0] if tokens else "unbekannt"
            tokens = tokens[1:]
        model = next((t for t in tokens if t not in MODEL_NOISE and not t.isdigit()), "")
        return f"{brand} {model}".strip()


# ── HTTP ────────────────────────────────────────────────────────────────────

class Http:
    def __init__(self):
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "de-DE,de;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })

    def get(self, url: str):
        for attempt in range(1, MAX_RETRIES + 1):
            wait = REQUEST_DELAY_SECONDS - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                resp = self.session.get(url, timeout=TIMEOUT_SECONDS)
            except requests.RequestException as exc:
                log.warning("GET %s fehlgeschlagen (%s/%s): %s", url, attempt, MAX_RETRIES, exc)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                time.sleep(int(resp.headers.get("Retry-After", 5 * attempt)))
                continue
            if 400 <= resp.status_code < 500:
                log.warning("GET %s -> HTTP %s", url, resp.status_code)
                return None
            time.sleep(2 ** attempt)
        log.error("GET %s endgueltig fehlgeschlagen", url)
        return None


# ── Geocoding (PLZ -> Koordinaten, mit Cache im State) ──────────────────────

class Geocoder:
    def __init__(self, http: Http, cache: dict):
        self.http = http
        self.cache = cache

    def distance(self, zip_code: str | None) -> float | None:
        if not zip_code:
            return None
        for country in ("de", "at", "ch"):
            ck = f"{country}:{zip_code}"
            if ck in self.cache:
                hit = self.cache[ck]
                if hit:
                    return round(haversine_km(HOME_LAT, HOME_LON, hit[0], hit[1]), 1)
                continue
            resp = self.http.get(f"https://api.zippopotam.us/{country}/{zip_code}")
            if resp is None:
                self.cache[ck] = None
                continue
            try:
                places = resp.json().get("places") or []
                lat, lon = float(places[0]["latitude"]), float(places[0]["longitude"])
            except (ValueError, KeyError, IndexError, TypeError):
                self.cache[ck] = None
                continue
            self.cache[ck] = [lat, lon]
            return round(haversine_km(HOME_LAT, HOME_LON, lat, lon), 1)
        return None


# ── Quelle: Bikemarkt ───────────────────────────────────────────────────────

def guess_brand(title: str) -> str | None:
    low = title.lower()
    for brand in sorted(BRANDS, key=len, reverse=True):
        if low.startswith(brand.lower()):
            return brand
    return None


def guess_condition(text: str) -> str | None:
    low = text.lower()
    for needle, label in [
        ("gebraucht, wie neu", "gebraucht, wie neu"),
        ("used, like new", "gebraucht, wie neu"),
        ("defekt", "defekt"), ("gebraucht", "gebraucht"),
        ("used", "gebraucht"), ("neu", "neu"), ("new", "neu"),
    ]:
        if needle in low:
            return label
    return None


def container_with_price(anchor, max_up: int = 6):
    """Vom Artikel-Link nach oben klettern, bis ein Preis im Text steht.

    Bewusst ohne CSS-Klassen: das Markup aendert sich oefter als die
    Tatsache, dass Titel und Preis im selben Kasten stehen.
    """
    node = anchor
    for _ in range(max_up):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        if "€" in text and len(text) < 1200:
            return node
    return anchor.parent or anchor


def parse_bikemarkt_page(html_text: str) -> list[Listing]:
    soup = BeautifulSoup(html_text, "lxml")
    out, seen = [], set()
    for anchor in soup.select('a[href*="/article/"]'):
        href = anchor.get("href", "")
        m = ARTICLE_RE.search(href)
        if not m or m.group(1) in seen:
            continue
        title = (anchor.get("title") or anchor.get_text(" ", strip=True) or "").strip()
        title = re.sub(r"\s+kaufen$", "", title).strip()
        if len(title) < 6:
            continue
        container = container_with_price(anchor)
        block = container.get_text(" ", strip=True)
        price = parse_price(block)
        if price is None:
            continue
        seen.add(m.group(1))
        out.append(Listing(
            source="bikemarkt",
            source_id=m.group(1),
            title=title,
            price_eur=price,
            url=(href if href.startswith("http") else BIKEMARKT_BASE + href).split("?")[0],
            brand=guess_brand(title),
            condition=guess_condition(block),
            seller_type="shop" if ("Zum Shop" in str(container) or "Gewerblich" in block) else "private",
        ))
    return out


def fetch_bikemarkt(http: Http) -> list[Listing]:
    found: dict[str, Listing] = {}
    for category in BIKEMARKT_CATEGORIES:
        for page in range(1, BIKEMARKT_MAX_PAGES + 1):
            url = f"{BIKEMARKT_BASE}/category/{category}-gravel-bike?page={page}"
            resp = http.get(url)
            if resp is None:
                break
            items = parse_bikemarkt_page(resp.text)
            if not items:
                break
            for item in items:
                found.setdefault(item.key, item)
            log.info("bikemarkt kat=%s seite=%s -> %s Inserate", category, page, len(items))
    return list(found.values())


def enrich_location(http: Http, listing: Listing) -> None:
    """Detailseite laden, um PLZ/Ort und Versandhinweis zu bekommen."""
    resp = http.get(listing.url)
    if resp is None:
        return
    text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
    listing.shipping = bool(re.search(r"versand (möglich|innerhalb|nach)", text, re.I)
                            or re.search(r"shipping (possible|within)", text, re.I))
    m = re.search(r"\b(\d{5})\s+([A-ZÄÖÜ][\wäöüß.\-]+(?:\s[A-ZÄÖÜ][\wäöüß.\-]+)?)", text)
    if m:
        listing.zip_code = m.group(1)
        listing.location = f"{m.group(1)} {m.group(2)}"


# ── Quelle: buycycle ────────────────────────────────────────────────────────

def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def parse_buycycle_page(html_text: str) -> list[Listing]:
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
            item = Listing("buycycle", sid, name.strip(), price,
                           url if url.startswith("http") else BUYCYCLE_BASE + url,
                           brand=brand if isinstance(brand, str) else None,
                           seller_type="marketplace", shipping=True)
            out.setdefault(item.key, item)
    if out:
        return list(out.values())

    # 2) Eingebettetes Next.js-JSON
    script = soup.select_one("script#__NEXT_DATA__")
    if script and script.string:
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            data = None
        for node in walk(data or {}):
            if not {"id", "price"} <= set(node):
                continue
            title = node.get("name") or node.get("title") or " ".join(
                str(node.get(k, "")) for k in ("brand", "family", "model")).strip()
            price = normalize_number(str(node.get("price")))
            if not title or not price:
                continue
            slug = node.get("slug") or node.get("id")
            item = Listing("buycycle", node["id"], title, price,
                           f"{BUYCYCLE_BASE}/de-de/bike/{slug}",
                           brand=node.get("brand") if isinstance(node.get("brand"), str) else None,
                           seller_type="marketplace", shipping=True)
            out.setdefault(item.key, item)
    if out:
        return list(out.values())

    # 3) Stumpfes HTML
    for anchor in soup.select('a[href*="/bike/"]'):
        href = anchor.get("href", "")
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
        title = (anchor.get("title") or anchor.get_text(" ", strip=True)).strip()
        if not price or len(title) < 6:
            continue
        item = Listing("buycycle", m.group(1), title, price,
                       href if href.startswith("http") else BUYCYCLE_BASE + href,
                       seller_type="marketplace", shipping=True)
        out.setdefault(item.key, item)
    return list(out.values())


def fetch_buycycle(http: Http) -> list[Listing]:
    found: dict[str, Listing] = {}
    for page in range(1, BUYCYCLE_MAX_PAGES + 1):
        resp = http.get(f"{BUYCYCLE_BASE}/de-de/shop?query=gravel&page={page}")
        if resp is None:
            break
        items = parse_buycycle_page(resp.text)
        if not items:
            log.warning("buycycle: Seite %s ohne Treffer", page)
            break
        for item in items:
            found.setdefault(item.key, item)
        log.info("buycycle seite=%s -> %s Inserate", page, len(items))
    return list(found.values())


# ── State ───────────────────────────────────────────────────────────────────

class Store:
    MAX_PRICE_POINTS = 20
    MAX_MARKET_SAMPLES = 60
    STALE_DAYS = 45

    def __init__(self, path: str):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            log.info("Kein State gefunden — Erstlauf")
            self.data = {}
        self.data.setdefault("listings", {})
        self.data.setdefault("market", {})
        self.data.setdefault("geo", {})

    @property
    def is_first_run(self) -> bool:
        return not self.data["listings"]

    def get(self, key):
        return self.data["listings"].get(key)

    def record(self, listing: Listing) -> dict:
        entry = self.data["listings"].get(listing.key)
        if entry is None:
            entry = {"title": listing.title, "url": listing.url,
                     "first_seen": now_iso(),
                     "prices": [[now_iso(), listing.price_eur]], "alerted": {}}
            self.data["listings"][listing.key] = entry
        else:
            entry["title"] = listing.title
            if not entry["prices"] or entry["prices"][-1][1] != listing.price_eur:
                entry["prices"].append([now_iso(), listing.price_eur])
                entry["prices"] = entry["prices"][-self.MAX_PRICE_POINTS:]
        entry["last_seen"] = now_iso()
        entry["zip"] = listing.zip_code
        entry["location"] = listing.location
        entry["shipping"] = listing.shipping
        return entry

    def previous_price(self, key) -> float | None:
        entry = self.data["listings"].get(key)
        if not entry or len(entry["prices"]) < 2:
            return None
        return float(entry["prices"][-2][1])

    def add_market_sample(self, model_key, price):
        s = self.data["market"].setdefault(model_key, [])
        s.append(price)
        self.data["market"][model_key] = s[-self.MAX_MARKET_SAMPLES:]

    def market_samples(self, model_key) -> list:
        return self.data["market"].get(model_key, [])

    def already_alerted(self, key, reason, price) -> bool:
        hit = ((self.data["listings"].get(key) or {}).get("alerted") or {}).get(reason)
        return bool(hit) and price >= float(hit[1]) * 0.97

    def mark_alerted(self, key, reason, price):
        self.data["listings"][key].setdefault("alerted", {})[reason] = [now_iso(), price]

    def prune(self) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - self.STALE_DAYS * 86400
        drop = []
        for key, entry in self.data["listings"].items():
            try:
                if datetime.fromisoformat(entry.get("last_seen", "")).timestamp() < cutoff:
                    drop.append(key)
            except ValueError:
                continue
        for key in drop:
            del self.data["listings"][key]
        return len(drop)

    def save(self):
        self.data["last_run"] = now_iso()
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8")


# ── Filter & Bewertung ──────────────────────────────────────────────────────

def passes_filters(listing: Listing) -> bool:
    title = listing.title.lower()
    if not (MIN_PRICE_EUR <= listing.price_eur <= MAX_PRICE_EUR):
        return False
    if any(w.lower() in title for w in EXCLUDE_KEYWORDS):
        return False
    if INCLUDE_KEYWORDS and not any(w.lower() in title for w in INCLUDE_KEYWORDS):
        return False
    if FRAME_SIZES and not any(str(s).lower() in title for s in FRAME_SIZES):
        return False
    if listing.distance_km is not None:
        if listing.distance_km > MAX_DISTANCE_KM:
            return listing.shipping and INCLUDE_SHIPPING_OFFERS
        return True
    if listing.shipping and INCLUDE_SHIPPING_OFFERS:
        return True
    return INCLUDE_UNKNOWN_LOCATION


class Deal:
    def __init__(self, listing, reason, headline, score,
                 discount_pct=None, reference_price=None, previous_price=None):
        self.listing = listing
        self.reason = reason
        self.headline = headline
        self.score = score
        self.discount_pct = discount_pct
        self.reference_price = reference_price
        self.previous_price = previous_price


def evaluate(listing: Listing, store: Store) -> Deal | None:
    prev = store.previous_price(listing.key)
    if prev and prev > listing.price_eur:
        drop = (prev - listing.price_eur) / prev * 100
        if drop >= MIN_PRICE_DROP_PCT:
            return Deal(listing, "price_drop", f"Preis gesenkt −{drop:.0f}%",
                        score=drop + 10, discount_pct=drop, previous_price=prev)

    samples = store.market_samples(listing.model_key)
    if len(samples) >= MIN_SAMPLES_FOR_MEDIAN:
        ref = statistics.median(samples)
        if ref and listing.price_eur < ref:
            discount = (ref - listing.price_eur) / ref * 100
            if discount >= MIN_DISCOUNT_PCT:
                return Deal(listing, "under_market", f"{discount:.0f}% unter Marktwert",
                            score=discount, discount_pct=discount, reference_price=ref)
    return None


# ── Telegram ────────────────────────────────────────────────────────────────

class Telegram:
    ICONS = {"price_drop": "📉", "under_market": "🔥"}

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID fehlen — nur Log-Ausgabe")

    def send(self, text: str, preview: bool = True) -> bool:
        if not self.enabled:
            print(text)
            return False
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                      "link_preview_options": {"is_disabled": not preview}},
                timeout=20)
            if resp.status_code == 429:
                time.sleep(resp.json().get("parameters", {}).get("retry_after", 5) + 1)
                return self.send(text, preview)
            if resp.status_code != 200:
                log.error("Telegram %s: %s", resp.status_code, resp.text[:300])
                return False
            return True
        except requests.RequestException as exc:
            log.error("Telegram-Versand fehlgeschlagen: %s", exc)
            return False

    def send_deal(self, deal: Deal) -> bool:
        lg = deal.listing
        lines = [f"{self.ICONS.get(deal.reason, '🚲')} <b>{html.escape(deal.headline)}</b>",
                 f"<b>{html.escape(lg.title)}</b>"]
        price_line = f"💶 <b>{fmt_eur(lg.price_eur)}</b>"
        if deal.previous_price:
            price_line += f"  <s>{fmt_eur(deal.previous_price)}</s>"
        elif deal.reference_price:
            price_line += f"  (Median {fmt_eur(deal.reference_price)})"
        lines.append(price_line)

        meta = []
        if lg.distance_km is not None:
            meta.append(f"📍 {html.escape(lg.location or '?')} · {lg.distance_km:.0f} km")
        elif lg.shipping:
            meta.append("📦 Versand möglich")
        if lg.condition:
            meta.append(html.escape(lg.condition))
        if lg.seller_type == "shop":
            meta.append("🏪 Händler")
        if meta:
            lines.append(" · ".join(meta))

        lines.append(f'\n<a href="{html.escape(lg.url, quote=True)}">Zum Inserat →</a>')
        lines.append(f"<i>{lg.source}</i>")
        return self.send("\n".join(lines))


# ── Ablauf ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> int:
    http = Http()
    store = Store(STATE_FILE)
    geocoder = Geocoder(http, store.data["geo"])
    telegram = Telegram()

    silent = dry_run or (store.is_first_run and SEED_RUN_SILENT)
    if silent:
        log.info("Stiller Lauf — es wird nichts gesendet")

    listings: list[Listing] = []
    if BIKEMARKT_ENABLED:
        try:
            listings += fetch_bikemarkt(http)
        except Exception:
            log.exception("Bikemarkt fehlgeschlagen")
    if BUYCYCLE_ENABLED:
        try:
            listings += fetch_buycycle(http)
        except Exception:
            log.exception("buycycle fehlgeschlagen")
    log.info("%s Inserate eingesammelt", len(listings))

    for lg in listings:
        known = store.get(lg.key)
        if known and known.get("zip"):
            lg.zip_code = known["zip"]
            lg.location = known.get("location")
            lg.shipping = known.get("shipping", False)
        elif lg.source == "bikemarkt" and not known:
            try:
                enrich_location(http, lg)
            except Exception as exc:
                log.warning("Standort für %s nicht ermittelbar: %s", lg.url, exc)
        if not lg.zip_code and lg.location:
            m = ZIP_RE.search(lg.location)
            lg.zip_code = m.group(1) if m else None
        lg.distance_km = geocoder.distance(lg.zip_code)

    deals, kept = [], 0
    for lg in listings:
        if not passes_filters(lg):
            continue
        kept += 1
        store.record(lg)
        deal = evaluate(lg, store)
        store.add_market_sample(lg.model_key, lg.price_eur)
        if deal and not store.already_alerted(lg.key, deal.reason, lg.price_eur):
            deals.append(deal)

    deals.sort(key=lambda d: d.score, reverse=True)
    selected = deals[:MAX_ALERTS_PER_RUN]
    skipped = max(0, len(deals) - MAX_ALERTS_PER_RUN)
    log.info("%s Inserate im Filter, %s Deals", kept, len(deals))

    if silent:
        for deal in deals:
            log.info("[stumm] %s | %s | %s", deal.headline,
                     fmt_eur(deal.listing.price_eur), deal.listing.url)
            store.mark_alerted(deal.listing.key, deal.reason, deal.listing.price_eur)
    else:
        for deal in selected:
            if telegram.send_deal(deal):
                store.mark_alerted(deal.listing.key, deal.reason, deal.listing.price_eur)
            log.info("ALERT %s | %s | %s", deal.headline,
                     fmt_eur(deal.listing.price_eur), deal.listing.url)
        if skipped:
            telegram.send(f"… und {skipped} weitere Treffer (Limit pro Lauf).", preview=False)

    removed = store.prune()
    if removed:
        log.info("%s veraltete Inserate entfernt", removed)
    if not dry_run:
        store.save()
        log.info("State gespeichert: %s", STATE_FILE)
    return len(selected)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gravel Deal Bot")
    parser.add_argument("--dry-run", action="store_true",
                        help="nichts senden, nichts speichern")
    parser.add_argument("--test-telegram", action="store_true",
                        help="nur eine Testnachricht schicken")
    args = parser.parse_args()

    if args.test_telegram:
        tg = Telegram()
        ok = tg.send("✅ Gravel Deal Bot ist verbunden.", preview=False)
        print("Testnachricht verschickt" if ok else "Fehlgeschlagen — Token/Chat-ID prüfen")
        return 0 if ok else 1

    try:
        run(dry_run=args.dry_run)
    except Exception:
        log.exception("Lauf abgebrochen")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
