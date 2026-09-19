"""Datenklassen der Domaene: Listing, Profil, Deal.

Bewusst ohne jede I/O — nur Felder und ein paar abgeleitete Eigenschaften.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from gravelbot.config import MODEL_NOISE, RADTYPEN

_ZIP_RE = re.compile(r"\b(\d{5})\b")


@dataclass
class Listing:
    source: str
    source_id: str
    title: str
    price_eur: float
    url: str
    brand: str | None = None
    condition: str | None = None
    seller_type: str | None = None
    location: str | None = None
    shipping: bool = False
    zip_code: str | None = None
    distance_km: float | None = None
    radtyp: str | None = None

    # Neuware
    is_new: bool = False
    list_price_eur: float | None = None  # UVP / Streichpreis

    # Attribute (soweit erkennbar)
    frame_size: str | None = None
    year: int | None = None
    material: str | None = None
    groupset: str | None = None
    drivetrain: str | None = None  # "1x" oder "2x"

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
            if tokens[: len(bt)] == bt:
                tokens = tokens[len(bt) :]
        else:
            brand = tokens[0] if tokens else "unbekannt"
            tokens = tokens[1:]
        model = next((t for t in tokens if t not in MODEL_NOISE and not t.isdigit()), "")
        return f"{brand} {model}".strip()

    @property
    def discount_vs_list_pct(self) -> float | None:
        """Rabatt gegenueber UVP/Streichpreis, unabhaengig vom Gebrauchtmarkt-Median."""
        if not self.list_price_eur or self.list_price_eur <= self.price_eur:
            return None
        return (self.list_price_eur - self.price_eur) / self.list_price_eur * 100

    def guess_zip_from_location(self) -> None:
        if not self.zip_code and self.location:
            m = _ZIP_RE.search(self.location)
            if m:
                self.zip_code = m.group(1)


@dataclass
class Profil:
    """Das Suchprofil — ersetzt die frueheren Modulkonstanten in bot.py."""

    radtypen: list[str] = field(default_factory=lambda: ["gravel"])

    home_lat: float = 48.7758
    home_lon: float = 9.1829
    home_plz: str | None = None
    max_distance_km: int = 200

    include_unknown_location: bool = True
    include_shipping_offers: bool = True

    min_price_eur: float = 500
    max_price_eur: float = 3500

    exclude_keywords: list[str] = field(default_factory=list)
    include_keywords: list[str] = field(default_factory=list)
    frame_sizes: list[str] = field(default_factory=list)

    min_discount_pct: float = 15
    min_price_drop_pct: float = 7
    min_samples_for_median: int = 4
    max_alerts_per_run: int = 12
    seed_run_silent: bool = True

    digest_times: list[str] = field(default_factory=lambda: ["08:00", "19:00"])
    paused: bool = False

    def validate_radtypen(self) -> None:
        self.radtypen = [r for r in self.radtypen if r in RADTYPEN] or ["gravel"]


@dataclass
class Deal:
    listing: Listing
    reason: str
    headline: str
    score: float
    discount_pct: float | None = None
    reference_price: float | None = None
    previous_price: float | None = None
