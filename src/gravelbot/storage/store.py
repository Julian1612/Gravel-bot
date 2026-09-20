"""Der komplette Zustand: Laden, Speichern, Zugriff.

Ein Objekt, ein state.json — die einzige Stelle, die diese Datei liest
oder schreibt. Migrationen laufen automatisch beim Laden (siehe
storage.migrations), nicht per Hand.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gravelbot.models import Listing, Profil
from gravelbot.storage.migrations import migrate

log = logging.getLogger("gravel.store")

_PROFIL_FIELDS = {f.name for f in dataclasses.fields(Profil)}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    MAX_PRICE_POINTS = 20
    MAX_MARKET_SAMPLES = 60
    MAX_DIGEST_ENTRIES = 200
    STALE_DAYS = 45

    def __init__(self, path: str):
        self.path = Path(path)
        if self.path.exists():
            raw = self.path.read_text(encoding="utf-8")
            self.data: dict[str, Any] = migrate(dict(json.loads(raw)))
        else:
            log.info("Kein State gefunden — Erstlauf")
            self.data = migrate({})

    # ── Profil ──────────────────────────────────────────────────────────

    @property
    def profil(self) -> Profil:
        raw = {k: v for k, v in self.data.get("profil", {}).items() if k in _PROFIL_FIELDS}
        profil = Profil(**raw)
        profil.validate_radtypen()
        return profil

    def set_profil(self, profil: Profil) -> None:
        self.data["profil"] = dataclasses.asdict(profil)

    def reset_profil(self) -> None:
        self.data["profil"] = dataclasses.asdict(Profil())

    # ── Inserate ────────────────────────────────────────────────────────

    @property
    def is_first_run(self) -> bool:
        """Ob dies der allererste Lauf ist (steuert SEED_RUN_SILENT).

        Bewusst ein eigenes, persistentes Flag statt ``not listings`` —
        Listings werden nach STALE_DAYS geprunt, ein Profil, das laenger
        pausiert war, haette sonst irgendwann wieder 0 Listings und der Bot
        wuerde faelschlich wieder in den stillen Erstlauf-Modus fallen und
        echte Deals eine Runde lang verschlucken.
        """
        return not self.data.get("erstlauf_abgeschlossen", False)

    def get(self, key: str) -> dict | None:
        return self.data["listings"].get(key)

    def record(self, listing: Listing) -> dict:
        self.data["erstlauf_abgeschlossen"] = True
        entry = self.data["listings"].get(listing.key)
        if entry is None:
            entry = {
                "title": listing.title,
                "url": listing.url,
                "source": listing.source,
                "first_seen": now_iso(),
                "prices": [[now_iso(), listing.price_eur]],
                "alerted": {},
            }
            self.data["listings"][listing.key] = entry
        else:
            entry["title"] = listing.title
            if not entry["prices"] or entry["prices"][-1][1] != listing.price_eur:
                entry["prices"].append([now_iso(), listing.price_eur])
                entry["prices"] = entry["prices"][-self.MAX_PRICE_POINTS :]
        entry["last_seen"] = now_iso()
        entry["zip"] = listing.zip_code
        entry["location"] = listing.location
        entry["shipping"] = listing.shipping
        entry["is_new"] = listing.is_new
        entry["list_price"] = listing.list_price_eur
        return entry

    def previous_price(self, key: str) -> float | None:
        entry = self.data["listings"].get(key)
        if not entry or len(entry["prices"]) < 2:
            return None
        return float(entry["prices"][-2][1])

    def add_market_sample(self, model_key: str, price: float) -> None:
        s = self.data["market"].setdefault(model_key, [])
        s.append(price)
        self.data["market"][model_key] = s[-self.MAX_MARKET_SAMPLES :]

    def market_samples(self, model_key: str) -> list[float]:
        return self.data["market"].get(model_key, [])

    def add_neupreis_sample(self, model_key: str, list_price: float) -> None:
        s = self.data["neupreise"].setdefault(model_key, [])
        s.append(list_price)
        self.data["neupreise"][model_key] = s[-self.MAX_MARKET_SAMPLES :]

    def neupreis_samples(self, model_key: str) -> list[float]:
        return self.data["neupreise"].get(model_key, [])

    def already_alerted(self, key: str, reason: str, price: float) -> bool:
        listing = self.data["listings"].get(key) or {}
        hit = (listing.get("alerted") or {}).get(reason)
        if not hit:
            return False
        return price >= float(hit[1]) * 0.97

    def mark_alerted(self, key: str, reason: str, price: float) -> None:
        entry = self.data["listings"].get(key)
        if entry is None:
            log.warning("mark_alerted fuer unbekannten Key %s ignoriert (record() vergessen?)", key)
            return
        entry.setdefault("alerted", {})[reason] = [now_iso(), price]

    def prune(self) -> int:
        cutoff = datetime.now(UTC).timestamp() - self.STALE_DAYS * 86400
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

    def treffer_stats(self, profil_check) -> tuple[int, int]:
        """(passende Inserate im Bestand, davon in den letzten 7 Tagen neu) —
        fuer /profil, damit ein leerlaufendes Profil sofort auffaellt."""
        cutoff = datetime.now(UTC).timestamp() - 7 * 86400
        passend, neu = 0, 0
        for entry in self.data["listings"].values():
            if not profil_check(entry):
                continue
            passend += 1
            try:
                if datetime.fromisoformat(entry.get("first_seen", "")).timestamp() >= cutoff:
                    neu += 1
            except ValueError:
                continue
        return passend, neu

    # ── Merkliste (Watchlist) ───────────────────────────────────────────

    def merkliste_add(self, listing: Listing) -> None:
        self.merkliste_add_key(listing.key, listing.title, listing.url)

    def merkliste_add_key(self, key: str, title: str, url: str) -> None:
        self.data["merkliste"][key] = {"title": title, "url": url, "added_at": now_iso()}

    def merkliste_remove(self, key: str) -> bool:
        return self.data["merkliste"].pop(key, None) is not None

    def merkliste_items(self) -> dict[str, dict]:
        return self.data["merkliste"]

    # ── Blockliste ──────────────────────────────────────────────────────

    def block_seller(self, name: str) -> None:
        sellers = self.data["blockliste"]["verkaeufer"]
        if name not in sellers:
            sellers.append(name)

    def unblock_seller(self, name: str) -> bool:
        sellers = self.data["blockliste"]["verkaeufer"]
        if name in sellers:
            sellers.remove(name)
            return True
        return False

    def is_seller_blocked(self, name: str | None) -> bool:
        return bool(name) and name in self.data["blockliste"]["verkaeufer"]

    def block_listing(self, key: str, title: str, url: str, reason: str = "") -> None:
        self.data["blockliste"]["inserate"][key] = {
            "title": title,
            "url": url,
            "reason": reason,
            "blocked_at": now_iso(),
        }

    def unblock_listing(self, key: str) -> bool:
        return self.data["blockliste"]["inserate"].pop(key, None) is not None

    def is_listing_blocked(self, key: str) -> bool:
        return key in self.data["blockliste"]["inserate"]

    def blockliste_view(self) -> dict:
        return self.data["blockliste"]

    # ── Digest-Puffer ───────────────────────────────────────────────────

    def digest_add(self, eintrag: dict) -> None:
        puffer = self.data["digest_puffer"]
        puffer.append(eintrag)
        if len(puffer) > self.MAX_DIGEST_ENTRIES:
            # Sollte der Digest aus irgendeinem Grund nie geleert werden
            # (z.B. digest_times leer/kaputt), waechst state.json sonst
            # unbegrenzt und der irgendwann verschickte Digest waere riesig.
            log.warning(
                "Digest-Puffer ueber %s Eintraege — aelteste werden verworfen", self.MAX_DIGEST_ENTRIES
            )
            self.data["digest_puffer"] = puffer[-self.MAX_DIGEST_ENTRIES :]

    def digest_pop_all(self) -> list[dict]:
        puffer = self.data["digest_puffer"]
        self.data["digest_puffer"] = []
        return puffer

    # ── Telegram-Offset & Dialogzustand ─────────────────────────────────

    @property
    def telegram_offset(self) -> int:
        return int(self.data.get("telegram_offset", 0))

    @telegram_offset.setter
    def telegram_offset(self, value: int) -> None:
        self.data["telegram_offset"] = value

    def get_dialog(self, chat_id: str) -> dict | None:
        return self.data["dialoge"].get(str(chat_id))

    def set_dialog(self, chat_id: str, state: dict) -> None:
        self.data["dialoge"][str(chat_id)] = state

    def clear_dialog(self, chat_id: str) -> None:
        self.data["dialoge"].pop(str(chat_id), None)

    # ── Speichern ───────────────────────────────────────────────────────

    def save(self) -> None:
        """Schreibt atomar: erst in eine Temp-Datei, dann per os.replace an Ort
        und Stelle. Ein Absturz oder Kill mitten im write_text() wuerde sonst
        ein halb geschriebenes, kaputtes state.json hinterlassen — und jeder
        folgende Lauf wuerde schon beim Laden mit einem JSON-Fehler abbrechen.
        """
        self.data["last_run"] = now_iso()
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)
