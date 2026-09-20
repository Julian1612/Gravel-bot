"""Zustandsmaschine fuer /setup und die Einzelfeld-Bearbeitung aus /profil.

Reine Funktionen: Eingabe (Text oder Callback-Daten) rein, neuer
Dialogzustand oder Fehlermeldung raus. Kein Telegram-I/O hier — das
uebernimmt telegram/router.py. Dadurch ist die komplette
Ablauflogik ohne Mocks testbar.

Ein Durchlauf durch /setup zieht sich ueber mehrere Cron-Laeufe (siehe
telegram/client.py) — der Zustand zwischen zwei Schritten liegt deshalb
in state.json (Store.get_dialog/set_dialog), nicht im Prozessspeicher.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from gravelbot.config import RADTYP_LABELS, RADTYPEN

RADTYP = "radtyp"
STANDORT = "standort"
RADIUS = "radius"
PREISRAHMEN = "preisrahmen"
SCHWELLE = "schwelle"
ZEITEN = "zeiten"

SETUP_SCHRITTE = [RADTYP, STANDORT, RADIUS, PREISRAHMEN, SCHWELLE, ZEITEN]

_PLZ_RE = re.compile(r"^\d{4,5}$")
_ZEIT_HHMM_RE = re.compile(r"^(\d{1,2})[:.](\d{2})$")
_ZEIT_KOMPAKT_RE = re.compile(r"^(\d{3,4})$")
_ZEIT_STUNDE_RE = re.compile(r"^(\d{1,2})$")


@dataclass
class DialogZustand:
    flow: str  # "setup" oder "edit"
    schritt: str
    daten: dict = field(default_factory=dict)
    rueckkehr: str | None = None  # bei "edit": nach Abschluss zurueck zu /profil

    def to_dict(self) -> dict:
        return {"flow": self.flow, "schritt": self.schritt, "daten": self.daten, "rueckkehr": self.rueckkehr}

    @classmethod
    def from_dict(cls, d: dict) -> DialogZustand:
        return cls(
            flow=d["flow"], schritt=d["schritt"], daten=d.get("daten", {}), rueckkehr=d.get("rueckkehr")
        )


def setup_starten() -> DialogZustand:
    return DialogZustand(flow="setup", schritt=SETUP_SCHRITTE[0], daten={"radtypen": []})


def feld_bearbeiten(feld: str, aktuelle_daten: dict) -> DialogZustand:
    return DialogZustand(flow="edit", schritt=feld, daten=dict(aktuelle_daten), rueckkehr="profil")


def naechster_schritt(schritt: str) -> str | None:
    idx = SETUP_SCHRITTE.index(schritt)
    return SETUP_SCHRITTE[idx + 1] if idx + 1 < len(SETUP_SCHRITTE) else None


def toggle_radtyp(ausgewaehlt: list[str], radtyp: str) -> list[str]:
    ausgewaehlt = list(ausgewaehlt)
    if radtyp in ausgewaehlt:
        ausgewaehlt.remove(radtyp)
    elif radtyp in RADTYPEN:
        ausgewaehlt.append(radtyp)
    return ausgewaehlt


def parse_plz(text: str) -> tuple[str | None, str | None]:
    text = (text or "").strip()
    if not _PLZ_RE.match(text):
        return None, "Bitte eine gueltige Postleitzahl schicken (4-5 Ziffern), z.B. 70173."
    return text, None


def parse_radius(text: str) -> tuple[int | None, str | None]:
    text = (text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 2000):
        return None, "Bitte eine Zahl in km schicken, z.B. 100."
    return int(text), None


def parse_preisrahmen(text: str) -> tuple[tuple[float, float] | None, str | None]:
    # Bewusst eine Alternation aus literalen Trennern, kein Zeichensatz:
    # [-–bis] wuerde als Zeichenklasse jedes einzelne Zeichen '-','–','b',
    # 'i','s' matchen (z.B. auch "500 sbi 3500") statt nur "-", "–" oder das
    # Wort "bis" als Ganzes.
    m = re.match(r"^\s*(\d+)\s*(?:-|–|bis)\s*(\d+)\s*€?\s*$", (text or "").strip(), re.I)
    if not m:
        return None, "Bitte als 'MIN-MAX' schicken, z.B. 500-3500."
    lo, hi = float(m.group(1)), float(m.group(2))
    if lo >= hi:
        return None, "Der Mindestpreis muss kleiner als der Hoechstpreis sein."
    return (lo, hi), None


def parse_prozent(text: str) -> tuple[float | None, str | None]:
    text = (text or "").strip().rstrip("%")
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None, "Bitte eine Zahl in Prozent schicken, z.B. 15."
    if not (0 < value <= 90):
        return None, "Bitte einen Wert zwischen 1 und 90 Prozent schicken."
    return value, None


def _parse_eine_uhrzeit(text: str) -> str | None:
    """Sehr tolerant: '8', '8:00', '08:00', '8.30', '800', '1930' — alles
    wird zu 'HH:MM' normalisiert. Menschen tippen selten konsequent
    fuehrende Nullen oder ueberhaupt einen Doppelpunkt; ein strenges
    Format nur deswegen abzulehnen bremst nur aus, ohne echten Nutzen."""
    text = text.strip()
    stunde: int | None = None
    minute = 0

    m = _ZEIT_HHMM_RE.match(text)
    if m:
        stunde, minute = int(m.group(1)), int(m.group(2))
    elif _ZEIT_KOMPAKT_RE.match(text):
        stunde, minute = int(text[:-2]), int(text[-2:])
    elif _ZEIT_STUNDE_RE.match(text):
        stunde = int(text)

    if stunde is None or not (0 <= stunde <= 23) or not (0 <= minute <= 59):
        return None
    return f"{stunde:02d}:{minute:02d}"


def parse_zeiten(text: str) -> tuple[list[str] | None, str | None]:
    teile = [t.strip() for t in re.split(r"[,;]", text or "") if t.strip()]
    if not teile:
        return None, "Bitte mindestens eine Uhrzeit schicken, z.B. 8,19 oder 08:00,19:00."
    normalisiert = []
    for t in teile:
        uhrzeit = _parse_eine_uhrzeit(t)
        if uhrzeit is None:
            return None, f"'{t}' ist keine gueltige Uhrzeit — z.B. 8, 8:00 oder 08:00."
        normalisiert.append(uhrzeit)
    return normalisiert, None


def parse_radtypen(text: str) -> tuple[list[str] | None, str | None]:
    """Erlaubt, die komplette Radtyp-Auswahl in einer Nachricht als Text zu
    schicken (z.B. 'gravel, rennrad') statt jeden Button einzeln
    anzutippen — das umgeht das Mehrfach-Tap-Problem bei Inline-Buttons
    komplett, siehe ADR 0007."""
    kandidaten = [t.strip().lower() for t in re.split(r"[,;/\s]+", text or "") if t.strip()]
    label_zu_key = {label.lower(): key for key, label in RADTYP_LABELS.items()}
    treffer: list[str] = []
    for kandidat in kandidaten:
        key = kandidat if kandidat in RADTYPEN else label_zu_key.get(kandidat)
        if key and key not in treffer:
            treffer.append(key)
    if not treffer:
        return None, None
    return treffer, None
