"""Zentrale Einstellungen — aus Environment-Variablen mit Defaults.

Alles, was frueher als Modulkonstante quer in bot.py stand, ist hier
gesammelt. Wer Schwellenwerte oder Zeiten dauerhaft aendern will, kann das
entweder hier als Default tun oder zur Laufzeit ueber /schwelle, /zeiten
und /setup im Profil (state.json) — das Profil hat Vorrang vor den Defaults
hier.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Kein HOME_LAT/HOME_LON hier: der Standort ist seit dem Profil-Umbau
    # reine Laufzeit-Konfiguration (Profil.home_lat/home_lon in state.json,
    # per /setup oder direktem Bearbeiten von state.json aenderbar) — ein
    # Deploy-Zeit-Env-Var haette hier ohnehin nur den Erstlauf-Default
    # beeinflusst und wurde nirgends mehr gelesen.
    state_file: str = field(default_factory=lambda: os.environ.get("STATE_FILE", "state.json"))

    user_agent: str = "gravel-deal-bot/1.0 (persoenlicher Preisalarm)"
    request_delay_seconds: float = field(default_factory=lambda: _env_float("REQUEST_DELAY_SECONDS", 1.2))
    timeout_seconds: int = field(default_factory=lambda: _env_int("TIMEOUT_SECONDS", 20))
    max_retries: int = field(default_factory=lambda: _env_int("MAX_RETRIES", 3))

    bikemarkt_max_pages: int = field(default_factory=lambda: _env_int("BIKEMARKT_MAX_PAGES", 6))
    buycycle_max_pages: int = field(default_factory=lambda: _env_int("BUYCYCLE_MAX_PAGES", 3))
    shop_max_pages: int = field(default_factory=lambda: _env_int("SHOP_MAX_PAGES", 3))

    # Freitext-Suche: Deckel gegen Timeouts im Action-Lauf
    suche_max_seiten_pro_quelle: int = 2
    suche_gesamtlimit: int = 60

    # eBay Browse API — Credentials kommen NIE in state.json, nur aus Env
    ebay_client_id: str = field(default_factory=lambda: os.environ.get("EBAY_CLIENT_ID", ""))
    ebay_client_secret: str = field(default_factory=lambda: os.environ.get("EBAY_CLIENT_SECRET", ""))
    ebay_marketplace_id: str = "EBAY_DE"
    # Kategorie "Fahrraeder" auf ebay.de, verifiziert gegen echte Kategorie-URLs
    # (https://www.ebay.de/b/Fahrrader/177831/...)
    ebay_category_id: str = "177831"

    telegram_bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    # True, sobald ein Telegram-Webhook eingerichtet ist (siehe
    # docs/adr/0006-telegram-webhook.md) — dann darf der reguläre Cron-Lauf
    # nicht mehr per getUpdates pollen, das kollidiert mit dem Webhook.
    telegram_webhook_mode: bool = field(
        default_factory=lambda: os.environ.get("TELEGRAM_WEBHOOK_MODE", "").strip() == "1"
    )


BRANDS = [
    "Rose Bikes",
    "NS Bikes",
    "Marin Bikes",
    "Basic Bikes",
    "Crossworx Bikes",
    "Dinolfo Cycles",
    "J.Guillem",
    "VanNicholas",
    "Van Nicholas",
    "Cannondale",
    "Specialized",
    "Bergamont",
    "Nukeproof",
    "Propain",
    "Cervélo",
    "Cervelo",
    "Santa Cruz",
    "Rocky Mountain",
    "Canyon",
    "Merida",
    "Giant",
    "Orbea",
    "Ridley",
    "Rondo",
    "Scott",
    "Trek",
    "Cube",
    "Kona",
    "Koga",
    "Niner",
    "Focus",
    "Stevens",
    "Storck",
    "Genesis",
    "Salsa",
    "Surly",
    "Open",
    "Ibis",
    "Norco",
    "Fuji",
    "Lapierre",
    "BMC",
    "Bianchi",
    "Wilier",
    "3T",
    "Cinelli",
    "Vitus",
    "Basso",
    "Pinarello",
    "Colnago",
]

MODEL_NOISE = {
    "gravel",
    "gravelbike",
    "bike",
    "rad",
    "carbon",
    "alu",
    "aluminium",
    "neu",
    "neuwertig",
    "gebraucht",
    "gr",
    "rh",
    "größe",
    "groesse",
    "wie",
    "top",
    "zustand",
    "cm",
    "de",
    "the",
    "mit",
    "und",
}

# Titel mit diesen Woertern werden immer verworfen — unabhaengig vom Profil.
# Gilt fuer alle Quellen, auch Neuware (keine Rahmensets, keine E-Bikes, keine Teile).
HARD_EXCLUDE = [
    "rahmenset",
    "frameset",
    "nur rahmen",
    "rahmen only",
    "frame only",
    "e-bike",
    "e-mtb",
    "e-rennrad",
    "pedelec",
    "ebike",
    "kinder",
    "kids",
    "gesucht",
    "suche ",
    "tausch gegen",
    "schaltwerk",
    "umwerfer",
    "laufradsatz",
    "laufrad ",
    "vorbau",
    "lenker",
    "sattelstütze",
    "kurbel",
    "kassette",
    "kette ",
]

RADTYPEN = ["gravel", "endurance_rennrad", "cyclocross", "rennrad"]

RADTYP_LABELS = {
    "gravel": "Gravel",
    "endurance_rennrad": "Endurance-Rennrad",
    "cyclocross": "Cyclocross",
    "rennrad": "Rennrad",
}

# Bikemarkt (MTB-News) hat keine eigenen Kategorien fuer Endurance-Rennrad
# oder Cyclocross — dort landet beides in "Rennrad" (17) bzw. der
# gemischten Kategorie "Rennrad & Gravel" (194). Naeherung, dokumentiert in
# docs/adr/0004-radtyp-mapping.md.
BIKEMARKT_CATEGORIES = {
    "gravel": [123],
    "rennrad": [17, 194],
    "endurance_rennrad": [17, 194],
    "cyclocross": [17, 194],
}

# buycycle durchsucht per Freitext-Query, hat kein festes Kategorieschema.
BUYCYCLE_QUERY = {
    "gravel": "gravel",
    "rennrad": "rennrad",
    "endurance_rennrad": "rennrad",
    "cyclocross": "cyclocross",
}

EBAY_QUERY = {
    "gravel": "Gravelbike",
    "rennrad": "Rennrad",
    "endurance_rennrad": "Rennrad",
    "cyclocross": "Cyclocross",
}

# Canyon-Outlet-Kategorien (item_category2 im data-gtm-impression-Attribut
# der Produktkacheln), verifiziert gegen echtes HTML von canyon.com/outlet.
CANYON_CATEGORY = {
    "gravel": "Gravel Outlet",
    "rennrad": "Road Outlet",
    "endurance_rennrad": "Road Outlet",
    "cyclocross": "Road Outlet",
}

# Rose-Sale-Kategorie-IDs aus der Sidebar-Facette auf rosebikes.de/sale/fahrraeder
ROSE_SALE_CATEGORY = {
    "gravel": "1209",
    "rennrad": "151",
    "endurance_rennrad": "151",
    "cyclocross": "151",
}

# Bike-Components: eigene Komplettbike-Kategorien je Radtyp (keine separate
# Endurance-/Cyclocross-Kategorie im Shop vorhanden).
BIKE_COMPONENTS_CATEGORY_PATH = {
    "gravel": "/de/fahrraeder/rennraeder/gravelbike/",
    "rennrad": "/de/fahrraeder/rennraeder/rennrad/",
    "endurance_rennrad": "/de/fahrraeder/rennraeder/rennrad/",
    "cyclocross": "/de/fahrraeder/rennraeder/rennrad/",
}
