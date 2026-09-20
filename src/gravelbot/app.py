"""Orchestrierung eines Laufs — sonst nichts. Keine Geschaeftslogik hier,
nur das Zusammenstecken von Quellen, Store, Scoring und Telegram in der
richtigen Reihenfolge.

Zwei Einstiegspunkte:

- ``run()`` — der reguläre Cron-Lauf (scan.yml): Telegram-Updates per
  getUpdates abholen (nur im Polling-Modus, siehe
  Settings.telegram_webhook_mode), dann scannen und melden.
- ``handle_single_update()`` — fuer den optionalen Telegram-Webhook
  (telegram-update.yml, per repository_dispatch ausgeloest): verarbeitet
  genau ein bereits vorliegendes Update sofort, ohne auf den naechsten
  Cron-Lauf zu warten. Ein vollstaendiger Scan laeuft dabei nur, wenn das
  Update selbst /scan ausgeloest hat — sonst wuerde jede /profil-Anfrage
  einen kompletten Multi-Quellen-Scan lostreten. Siehe
  docs/adr/0006-telegram-webhook.md.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from gravelbot.config import Settings
from gravelbot.enrich.attributes import apply_attributes
from gravelbot.enrich.geocode import Geocoder
from gravelbot.http import Http
from gravelbot.models import Listing
from gravelbot.scoring.evaluate import evaluate
from gravelbot.scoring.filters import passes_filters
from gravelbot.sources.base import Quelle
from gravelbot.sources.registry import QuellenLauf, alle_quellen, durchsuche_alle
from gravelbot.storage.store import Store
from gravelbot.telegram.client import Telegram
from gravelbot.telegram.router import Router
from gravelbot.telegram.views import render_deal

log = logging.getLogger("gravel.app")

DIGEST_ZEITZONE = ZoneInfo("Europe/Berlin")
DIGEST_FENSTER_MINUTEN = 20


def _anreichern(listing: Listing, store: Store, geocoder: Geocoder, quellen_by_name: dict) -> None:
    known = store.get(listing.key)
    if known and known.get("zip"):
        listing.zip_code = known["zip"]
        listing.location = known.get("location")
        listing.shipping = known.get("shipping", listing.shipping)
    elif not known:
        quelle = quellen_by_name.get(listing.source)
        if quelle is not None:
            try:
                quelle.details(listing)
            except Exception:
                log.warning("Detail-Anreicherung fuer %s fehlgeschlagen", listing.url, exc_info=True)
    listing.guess_zip_from_location()
    listing.distance_km = geocoder.distance(listing.zip_code)
    apply_attributes(listing)


def _ist_digest_zeit(digest_times: list[str], jetzt: datetime | None = None) -> bool:
    jetzt = (jetzt or datetime.now(DIGEST_ZEITZONE)).astimezone(DIGEST_ZEITZONE)
    aktuelle_minuten = jetzt.hour * 60 + jetzt.minute
    for zeit in digest_times:
        try:
            h, m = (int(x) for x in zeit.split(":"))
        except ValueError:
            continue
        ziel_minuten = h * 60 + m
        if abs(aktuelle_minuten - ziel_minuten) <= DIGEST_FENSTER_MINUTEN:
            return True
    return False


def _schreibe_zusammenfassung(
    berichte: list[QuellenLauf], gefiltert: int, gemeldet: int, laufzeit_s: float
) -> None:
    pfad = os.environ.get("GITHUB_STEP_SUMMARY")
    zeilen = ["## Gravel Scan Zusammenfassung", "", "| Quelle | Status | Treffer |", "| --- | --- | --- |"]
    for b in berichte:
        if not b.aktiv:
            status = f"übersprungen ({b.grund})"
        elif b.fehler:
            status = f"fehlgeschlagen ({b.fehler[:60]})"
        else:
            status = "ok"
        zeilen.append(f"| {b.name} | {status} | {b.treffer} |")
    zeilen += [
        "",
        f"- Inserate im Filter: **{gefiltert}**",
        f"- gemeldete Deals: **{gemeldet}**",
        f"- Laufzeit: **{laufzeit_s:.1f}s**",
    ]
    text = "\n".join(zeilen)
    log.info("\n%s", text)
    if pfad:
        with open(pfad, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def _scan_und_melden(
    store: Store,
    settings: Settings,
    http: Http,
    telegram: Telegram,
    quellen: list[Quelle],
    quellen_by_name: dict[str, Quelle],
    dry_run: bool,
) -> int:
    """Ein kompletter Scan-Durchlauf: alle Quellen abfragen, filtern,
    bewerten, melden. Getrennt von run()/handle_single_update(), damit
    beide Einstiegspunkte ihn aufrufen koennen (Cron-Lauf immer, Webhook-Lauf
    nur bei explizitem /scan).
    """
    start = time.monotonic()
    profil = store.profil
    geocoder = Geocoder(http, store.data["geo"], profil.home_lat, profil.home_lon)
    silent = dry_run or (store.is_first_run and profil.seed_run_silent)
    if silent:
        log.info("Stiller Lauf — es wird nichts gesendet")

    listings, berichte = durchsuche_alle(quellen, profil)
    log.info("%s Inserate eingesammelt", len(listings))

    for lg in listings:
        _anreichern(lg, store, geocoder, quellen_by_name)

    deals, kept = [], 0
    for lg in listings:
        if store.is_listing_blocked(lg.key):
            continue
        if not passes_filters(lg, profil):
            continue
        kept += 1
        store.record(lg)
        previous_price = store.previous_price(lg.key)
        market_samples = store.market_samples(lg.model_key)
        deal = evaluate(lg, profil, previous_price, market_samples)
        store.add_market_sample(lg.model_key, lg.price_eur)
        if lg.is_new and lg.list_price_eur:
            store.add_neupreis_sample(lg.model_key, lg.list_price_eur)
        if deal and not store.already_alerted(lg.key, deal.reason, lg.price_eur):
            deals.append(deal)

    deals.sort(key=lambda d: d.score, reverse=True)
    selected = deals[: profil.max_alerts_per_run]
    ueberschuss = deals[profil.max_alerts_per_run :]
    log.info("%s Inserate im Filter, %s Deals", kept, len(deals))

    if silent:
        for deal in deals:
            log.info(
                "[stumm] %s | %s | %s",
                deal.headline,
                f"{deal.listing.price_eur:.0f}€",
                deal.listing.url,
            )
            store.mark_alerted(deal.listing.key, deal.reason, deal.listing.price_eur)
    else:
        for deal in selected:
            keyboard = [
                [
                    {"text": "🔖 merken", "callback_data": f"merkliste:hinzufuegen:{deal.listing.key}"},
                    {"text": "🚫 blocken", "callback_data": f"blockliste:inserat_sperren:{deal.listing.key}"},
                ]
            ]
            if telegram.send(render_deal(deal), keyboard=keyboard) is not None or not telegram.enabled:
                store.mark_alerted(deal.listing.key, deal.reason, deal.listing.price_eur)
            log.info("ALERT %s | %s | %s", deal.headline, f"{deal.listing.price_eur:.0f}€", deal.listing.url)

        for deal in ueberschuss:
            store.digest_add({"text": render_deal(deal)})
            store.mark_alerted(deal.listing.key, deal.reason, deal.listing.price_eur)

        if _ist_digest_zeit(profil.digest_times):
            puffer = store.digest_pop_all()
            if puffer:
                kopf = f"📬 <b>Digest — {len(puffer)} weitere Treffer</b>\n\n"
                telegram.send(kopf + "\n\n".join(e["text"] for e in puffer[:20]))
                for rest_start in range(20, len(puffer), 20):
                    telegram.send("\n\n".join(e["text"] for e in puffer[rest_start : rest_start + 20]))

    removed = store.prune()
    if removed:
        log.info("%s veraltete Inserate entfernt", removed)

    laufzeit = time.monotonic() - start
    _schreibe_zusammenfassung(berichte, kept, len(selected), laufzeit)
    return len(selected)


def run(dry_run: bool = False, scan_only: bool = False) -> int:
    settings = Settings()
    http = Http(settings)
    store = Store(settings.state_file)
    telegram = Telegram(settings)
    quellen = alle_quellen(http, settings)
    quellen_by_name = {q.name: q for q in quellen}
    router = Router(telegram, store, http, settings, quellen)

    if not scan_only:
        router.verarbeite_updates()

    profil = store.profil
    if profil.paused and not router.scan_erzwingen and not dry_run:
        log.info("Profil pausiert — kein Scan in diesem Lauf")
        if not dry_run:
            store.save()
        return 0

    ergebnis = _scan_und_melden(store, settings, http, telegram, quellen, quellen_by_name, dry_run)

    if not dry_run:
        store.save()
        log.info("State gespeichert: %s", settings.state_file)
    return ergebnis


def handle_single_update(update: dict, dry_run: bool = False) -> int:
    """Verarbeitet genau ein Telegram-Update sofort (vom Webhook), ohne auf
    den naechsten Cron-Lauf zu warten. Scannt nur, wenn das Update selbst
    /scan ausgeloest hat.
    """
    settings = Settings()
    http = Http(settings)
    store = Store(settings.state_file)
    telegram = Telegram(settings)
    quellen = alle_quellen(http, settings)
    quellen_by_name = {q.name: q for q in quellen}
    router = Router(telegram, store, http, settings, quellen)

    router.verarbeite_ein_update(update)

    ergebnis = 0
    if router.scan_erzwingen:
        ergebnis = _scan_und_melden(store, settings, http, telegram, quellen, quellen_by_name, dry_run)

    if not dry_run:
        store.save()
        log.info("State gespeichert: %s", settings.state_file)
    return ergebnis
