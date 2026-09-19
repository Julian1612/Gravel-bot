"""Attributextraktion aus Titel/Beschreibungstext — reine Funktionen, kein I/O.

Arbeitet heuristisch mit Regex auf Freitext (Titel plus optional Text der
Detailseite). Erkennt nicht jedes Inserat zuverlaessig — das ist bei
freiem Verkaeufertext auch nicht moeglich — liefert aber deutlich mehr
Struktur als frueher (nur Marke/Zustand).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gravelbot.models import Listing

_FRAME_SIZE_LETTER_RE = re.compile(r"\b(?:gr\.?|rh|größe|groesse|size)\s*:?\s*(XXS|XS|S|M|L|XL|XXL)\b", re.I)
_FRAME_SIZE_NUMBER_RE = re.compile(
    r"\b(?:gr\.?|rh|größe|groesse|size)\s*:?\s*(\d{2})\b|\b(\d{2})\s*cm\b", re.I
)
_YEAR_RE = re.compile(r"\b(20(?:1[5-9]|2[0-9]))\b")
_DRIVETRAIN_RE = re.compile(r"\b([12])[\s-]?x(?:[\s-]?\d{1,2})?\b", re.I)

_MATERIAL_KEYWORDS = [
    ("carbon", "Carbon"),
    ("carbonfaser", "Carbon"),
    ("aluminium", "Aluminium"),
    ("alu", "Aluminium"),
    ("titan", "Titan"),
    ("stahl", "Stahl"),
    ("steel", "Stahl"),
]

# Reihenfolge wichtig: laengere/spezifischere Namen zuerst, damit z.B.
# "GRX Di2" nicht faelschlich nur als "105" erkannt wird.
_GROUPSET_KEYWORDS = [
    "dura-ace",
    "dura ace",
    "ultegra",
    "grx",
    "105",
    "red axs",
    "red",
    "force axs",
    "force",
    "rival axs",
    "rival",
    "apex axs",
    "apex",
    "tiagra",
    "sora",
    "claris",
    "xtr",
    "xt",
    "slx",
    "deore",
    "gx eagle",
    "gx",
    "x01",
    "xx1",
]


@dataclass
class ExtrahierteAttribute:
    frame_size: str | None = None
    year: int | None = None
    material: str | None = None
    groupset: str | None = None
    drivetrain: str | None = None


def extract_attributes(text: str) -> ExtrahierteAttribute:
    text = text or ""
    low = text.lower()

    frame_size = None
    m = _FRAME_SIZE_LETTER_RE.search(text)
    if m:
        frame_size = m.group(1).upper()
    else:
        m = _FRAME_SIZE_NUMBER_RE.search(text)
        if m:
            frame_size = m.group(1) or m.group(2)

    year = None
    m = _YEAR_RE.search(text)
    if m:
        year = int(m.group(1))

    material = next((label for needle, label in _MATERIAL_KEYWORDS if needle in low), None)

    groupset = None
    for needle in _GROUPSET_KEYWORDS:
        if needle in low:
            groupset = needle.upper() if len(needle) <= 4 else needle.title()
            break

    drivetrain = None
    m = _DRIVETRAIN_RE.search(text)
    if m:
        drivetrain = f"{m.group(1)}x"

    return ExtrahierteAttribute(
        frame_size=frame_size,
        year=year,
        material=material,
        groupset=groupset,
        drivetrain=drivetrain,
    )


def apply_attributes(listing: Listing, extra_text: str = "") -> None:
    """Traegt erkannte Attribute in ein Listing ein, ohne Vorhandenes zu ueberschreiben."""
    attrs = extract_attributes(f"{listing.title} {extra_text}")
    listing.frame_size = listing.frame_size or attrs.frame_size
    listing.year = listing.year or attrs.year
    listing.material = listing.material or attrs.material
    listing.groupset = listing.groupset or attrs.groupset
    listing.drivetrain = listing.drivetrain or attrs.drivetrain
