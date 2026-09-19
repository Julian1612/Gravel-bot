"""Versionierte Schema-Migrationen fuer state.json.

Jede Migration ist eine eigene Funktion, die von Version N auf N+1 hebt.
``migrate()`` wendet alle noch fehlenden Migrationen der Reihe nach an.
Bestehende Daten werden nie verworfen, nur um Defaults ergaenzt — siehe
tests/test_migrations.py fuer den Beweis anhand eines echten alten
state.json.
"""

from __future__ import annotations

from dataclasses import asdict

from gravelbot.models import Profil

CURRENT_SCHEMA_VERSION = 2


def _migrate_v1_to_v2(data: dict) -> dict:
    """Erste Version hatte nur listings/market/geo/last_run — keine
    Profil-/Dialog-/Merklisten-/Blocklisten-Struktur, kein schema_version.
    """
    data.setdefault("listings", {})
    data.setdefault("market", {})
    data.setdefault("geo", {})
    data.setdefault("neupreise", {})
    data.setdefault("merkliste", {})
    data.setdefault("blockliste", {"verkaeufer": [], "inserate": {}})
    data.setdefault("digest_puffer", [])
    data.setdefault("telegram_offset", 0)
    data.setdefault("dialoge", {})
    data.setdefault("profil", asdict(Profil()))
    return data


_MIGRATIONS = {
    1: _migrate_v1_to_v2,
}


def migrate(data: dict) -> dict:
    version = int(data.get("schema_version", 1))
    while version < CURRENT_SCHEMA_VERSION:
        data = _MIGRATIONS[version](data)
        version += 1
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    return data
