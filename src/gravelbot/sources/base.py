"""Gemeinsames Interface fuer alle Quellen plus Text-/Preis-Helfer.

Eine Quelle, die eine Exception wirft, darf den Lauf nicht abbrechen —
siehe sources.registry.durchsuche_alle, wo jede Quelle einzeln in
try/except laeuft.
"""

from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

from gravelbot.models import Listing, Profil

PRICE_RE = re.compile(r"(?:€\s*([\d.,]+)|([\d.,]+)\s*(?:€|EUR))")


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


def attr_str(tag: Any, name: str, default: str = "") -> str:
    """Attribut eines BeautifulSoup-Tags als str lesen.

    bs4 typisiert Attribute als ``str | list[str] | None`` (manche HTML-
    Attribute sind mehrwertig, z.B. class). Fuer unsere Zwecke ist es immer
    ein einzelner String — dieser Helfer macht das an einer Stelle explizit,
    statt das an jeder Aufrufstelle neu zu behandeln.
    """
    if tag is None:
        return default
    value = tag.get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def walk(node):
    """Rekursiv durch verschachteltes JSON laufen (dict/list) und jedes dict liefern."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


@runtime_checkable
class Quelle(Protocol):
    """Interface, das jede Datenquelle implementiert.

    ``volltext`` ist optional (nicht jede Quelle bietet eine Freitextsuche) —
    Quellen ohne eigene Implementierung erben die Default-Methode aus
    QuelleBasis, die eine leere Liste liefert.
    """

    name: str

    def aktiv(self) -> bool:
        """False, wenn z.B. Zugangsdaten fehlen. Wird geloggt, bricht nichts ab."""
        ...

    def inaktiv_grund(self) -> str | None:
        """Menschlich lesbarer Grund, warum aktiv() False ist (fuer /profil)."""
        ...

    def suchen(self, profil: Profil) -> list[Listing]:
        """Katalogdurchlauf entlang des Profils (Radtyp, Seitenlimits, ...)."""
        ...

    def volltext(self, query: str, max_seiten: int = 2) -> list[Listing]:
        """Freitextsuche fuer /suche. Default: nicht unterstuetzt -> leer."""
        ...

    def details(self, listing: Listing) -> None:
        """Optionale Anreicherung (z.B. Standort von der Detailseite)."""
        ...


class QuelleBasis:
    """Bequeme Basisklasse mit Default-Implementierungen der optionalen Methoden."""

    name = "quelle"

    def aktiv(self) -> bool:
        return True

    def inaktiv_grund(self) -> str | None:
        return None

    def volltext(self, query: str, max_seiten: int = 2) -> list[Listing]:
        return []

    def details(self, listing: Listing) -> None:
        return None
