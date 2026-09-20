from __future__ import annotations

import json

from gravelbot.storage.migrations import CURRENT_SCHEMA_VERSION, migrate
from gravelbot.storage.store import Store


def test_migrate_v1_adds_missing_keys_without_losing_data(fixture_path):
    raw = json.loads(fixture_path("state_v1.json").read_text(encoding="utf-8"))
    migrated = migrate(raw)

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    # Bestehende Daten bleiben erhalten
    assert "bikemarkt:1782147" in migrated["listings"]
    assert migrated["listings"]["bikemarkt:1782147"]["prices"] == [
        ["2026-08-01T10:00:00+00:00", 1799.0],
        ["2026-09-01T10:00:00+00:00", 1599.0],
    ]
    assert migrated["market"]["canyon grizl"] == [1599.0, 1699.0, 1899.0, 2099.0]
    assert migrated["geo"] == {"de:70173": [48.7784, 9.1815]}
    # Neue Strukturen mit sinnvollen Defaults ergaenzt
    assert migrated["profil"]["radtypen"] == ["gravel"]
    assert migrated["neupreise"] == {}
    assert migrated["merkliste"] == {}
    assert migrated["blockliste"] == {"verkaeufer": [], "inserate": {}}
    assert migrated["digest_puffer"] == []
    assert migrated["telegram_offset"] == 0
    assert migrated["dialoge"] == {}
    # Hatte schon Listings -> ist offensichtlich kein Erstlauf mehr
    assert migrated["erstlauf_abgeschlossen"] is True


def test_migrate_v1_marks_empty_state_as_first_run():
    migrated = migrate({})
    assert migrated["erstlauf_abgeschlossen"] is False


def test_migrate_defends_partial_blockliste_from_hand_edited_state():
    raw = {"schema_version": 1, "blockliste": {"verkaeufer": ["boese@example.test"]}}
    migrated = migrate(raw)
    assert migrated["blockliste"]["verkaeufer"] == ["boese@example.test"]
    assert migrated["blockliste"]["inserate"] == {}


def test_migrate_is_idempotent(fixture_path):
    raw = json.loads(fixture_path("state_v1.json").read_text(encoding="utf-8"))
    once = migrate(raw)
    twice = migrate(dict(once))
    assert once == twice


def test_store_loads_real_old_state_file(fixture_path, tmp_path):
    target = tmp_path / "state.json"
    target.write_text(fixture_path("state_v1.json").read_text(encoding="utf-8"), encoding="utf-8")

    store = Store(str(target))

    assert store.data["schema_version"] == CURRENT_SCHEMA_VERSION
    assert store.is_first_run is False
    assert store.get("bikemarkt:1782147") is not None
    assert store.profil.radtypen == ["gravel"]

    store.save()
    reloaded = json.loads(target.read_text(encoding="utf-8"))
    assert reloaded["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "bikemarkt:1782147" in reloaded["listings"]
