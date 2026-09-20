"""Verteilt eingehende Telegram-Befehle/Callbacks auf Dialoge, Views und den Store.

Orchestrierung mit I/O — die eigentliche Ablauflogik der Dialoge steckt in
telegram/dialogs.py (rein), das Rendering in telegram/views.py (rein).
Ein Lauf verarbeitet alle Updates seit dem letzten offset und schickt
sofort Antworten; ein /setup-Durchlauf zieht sich dadurch ueber mehrere
Cron-Laeufe (siehe telegram/client.py).
"""

from __future__ import annotations

import html
import logging

from gravelbot.config import BOT_COMMANDS
from gravelbot.enrich.geocode import Geocoder
from gravelbot.http import Http
from gravelbot.models import Profil
from gravelbot.sources.base import Quelle
from gravelbot.sources.registry import volltextsuche_alle
from gravelbot.storage.store import Store
from gravelbot.telegram import dialogs, views
from gravelbot.telegram.client import Telegram

log = logging.getLogger("gravel.telegram.router")

# Jeder dieser Befehle funktioniert IMMER, auch mitten in einem laufenden
# /setup- oder Einzelfeld-Dialog — siehe _nachricht(). Ohne das waere jede
# Nachricht, die nicht exakt das ist, was der aktuelle Dialogschritt
# erwartet, eine Sackgasse: der Nutzer haette keine Moeglichkeit mehr,
# rauszukommen, auch nicht mit /help oder /abbrechen.
_GLOBALE_BEFEHLE = frozenset(f"/{befehl}" for befehl, _ in BOT_COMMANDS) | {"/hilfe", "/?"}


class Router:
    def __init__(self, telegram: Telegram, store: Store, http: Http, settings, quellen: list[Quelle]):
        self.telegram = telegram
        self.store = store
        self.http = http
        self.settings = settings
        self.quellen = quellen
        self.scan_erzwingen = False

    def verarbeite_updates(self) -> None:
        """Polling-Pfad: alle Updates seit dem letzten offset abholen.

        Nur relevant, solange kein Telegram-Webhook eingerichtet ist —
        Telegram erlaubt getUpdates und Webhook nicht gleichzeitig (sonst
        liefert getUpdates einen Konflikt-Fehler). Mit aktivem Webhook
        (Settings.telegram_webhook_mode) uebernimmt verarbeite_ein_update()
        die Zustellung, siehe docs/adr/0006-telegram-webhook.md.
        """
        if not self.telegram.enabled or self.settings.telegram_webhook_mode:
            return
        updates = self.telegram.get_updates(self.store.telegram_offset)
        for update in updates:
            self.store.telegram_offset = update["update_id"] + 1
            try:
                self._verarbeite_update(update)
            except Exception:
                log.exception("Update %s fehlgeschlagen", update.get("update_id"))

    def verarbeite_ein_update(self, update: dict) -> None:
        """Webhook-Pfad: ein einzelnes, bereits vorliegendes Update sofort
        verarbeiten (kein getUpdates, kein Offset-Abgleich noetig — Telegram
        liefert per Webhook jedes Update genau einmal)."""
        update_id = update.get("update_id")
        if update_id is not None:
            self.store.telegram_offset = update_id + 1
        try:
            self._verarbeite_update(update)
        except Exception:
            log.exception("Update %s fehlgeschlagen", update_id)

    def _ist_autorisiert(self, chat_id: str) -> bool:
        """Nur der in TELEGRAM_CHAT_ID konfigurierte Chat darf den Bot steuern.

        Ohne diese Pruefung wuerde der Bot auf jede Nachricht von jedem
        Telegram-Nutzer reagieren, der seinen Benutzernamen kennt — /setup,
        /reset, /pause eingeschlossen. TELEGRAM_CHAT_ID ist kein Geheimnis,
        aber es ist die einzige Stelle, an der feststeht, wer der Besitzer ist.
        """
        return chat_id == self.settings.telegram_chat_id

    def _verarbeite_update(self, update: dict) -> None:
        if "callback_query" in update:
            cq = update["callback_query"]
            chat_id = str(cq["message"]["chat"]["id"])
            if not self._ist_autorisiert(chat_id):
                log.warning("Callback von nicht autorisiertem Chat %s ignoriert", chat_id)
                self.telegram.answer_callback_query(cq["id"])
                return
            self._callback(cq)
        elif "message" in update and "text" in update["message"]:
            message = update["message"]
            chat_id = str(message["chat"]["id"])
            if not self._ist_autorisiert(chat_id):
                log.warning("Nachricht von nicht autorisiertem Chat %s ignoriert", chat_id)
                return
            self._nachricht(message)

    # ── Nachrichten (Text) ──────────────────────────────────────────────

    @staticmethod
    def _normalisiere_befehl(wort: str) -> str:
        """ "@botname" abschneiden (Telegram haengt das in manchen Clients an,
        z.B. "/setup@gravel_bot") und den Slash optional machen — "setup"
        soll genauso funktionieren wie "/setup", damit man den Bot nicht
        erst "richtig" ansprechen muss."""
        cmd = wort.lower().split("@", 1)[0]
        if not cmd.startswith("/"):
            cmd = "/" + cmd
        return cmd

    def _nachricht(self, message: dict) -> None:
        chat_id = str(message["chat"]["id"])
        text = (message.get("text") or "").strip()
        erstes_wort = text.split(maxsplit=1)[0] if text else ""
        cmd = self._normalisiere_befehl(erstes_wort) if erstes_wort else ""
        dialog = self.store.get_dialog(chat_id)

        if dialog and cmd not in _GLOBALE_BEFEHLE:
            self._dialog_eingabe(chat_id, dialog, text, ist_callback=False)
            return
        if dialog and cmd in _GLOBALE_BEFEHLE:
            # Der Nutzer will offensichtlich etwas anderes als den laufenden
            # Dialog fortsetzen (z.B. /help, /profil oder ein neues /setup)
            # — den Dialog verwerfen, statt ihn als Sackgasse stehen zu
            # lassen. Das war der Kernbug: /help mitten in /setup fiel
            # bisher auf denselben "bitte Buttons benutzen"-Fehler zurueck
            # wie jede andere Nachricht, und es gab keinen Ausweg.
            self.store.clear_dialog(chat_id)
        self._befehl(chat_id, text)

    def _befehl(self, chat_id: str, text: str) -> None:
        teile = text.split(maxsplit=1)
        if not teile:
            # leere/nur-Whitespace-Nachricht (z.B. ein Sticker ohne Text) —
            # text.split() waere hier [] und ein direktes cmd, *rest = ...
            # wuerde mit ValueError abstuerzen.
            self.telegram.send(views.render_help(), chat_id=chat_id)
            return
        cmd, *rest = teile
        arg = rest[0] if rest else ""
        cmd = self._normalisiere_befehl(cmd)

        if cmd in ("/help", "/hilfe", "/?"):
            self.telegram.send(views.render_help(), chat_id=chat_id)
        elif cmd == "/abbrechen":
            # _nachricht() hat einen evtl. laufenden Dialog schon verworfen
            # (siehe _GLOBALE_BEFEHLE) — hier nur noch die Bestaetigung.
            self.telegram.send("✅ Abgebrochen.", chat_id=chat_id)
        elif cmd == "/start":
            self.telegram.send(views.render_start(), chat_id=chat_id)
        elif cmd == "/setup":
            zustand = dialogs.setup_starten()
            self.store.set_dialog(chat_id, zustand.to_dict())
            prompt, kb = views.render_setup_step(zustand.schritt, zustand.daten)
            self.telegram.send(prompt, chat_id=chat_id, keyboard=kb)
        elif cmd == "/profil":
            self._zeige_profil(chat_id)
        elif cmd == "/markt":
            self._zeige_markt(chat_id)
        elif cmd == "/merkliste":
            text_, kb = views.render_merkliste(self.store.merkliste_items())
            self.telegram.send(text_, chat_id=chat_id, keyboard=kb or None)
        elif cmd == "/zeiten":
            self._starte_einzelfeld(chat_id, dialogs.ZEITEN)
        elif cmd == "/schwelle":
            self._starte_einzelfeld(chat_id, dialogs.SCHWELLE)
        elif cmd == "/scan":
            self.scan_erzwingen = True
            text_ = "Scan wird in diesem Lauf mitgemacht — Ergebnisse folgen gleich."
            self.telegram.send(text_, chat_id=chat_id)
        elif cmd == "/pause":
            profil = self.store.profil
            profil.paused = not profil.paused
            self.store.set_profil(profil)
            text_ = "⏸️ Suche pausiert." if profil.paused else "▶️ Suche laeuft wieder."
            self.telegram.send(text_, chat_id=chat_id)
        elif cmd == "/reset":
            text_, kb = views.render_reset_bestaetigung()
            self.telegram.send(text_, chat_id=chat_id, keyboard=kb)
        elif cmd == "/suche":
            if not arg:
                text_ = "Bitte einen Suchbegriff angeben, z.B. /suche Canyon Grizl"
                self.telegram.send(text_, chat_id=chat_id)
            else:
                self._freitextsuche(chat_id, arg)
        else:
            self.telegram.send(views.render_help(), chat_id=chat_id)

    def _starte_einzelfeld(self, chat_id: str, feld: str) -> None:
        aktuelles = _profil_als_dialogdaten(self.store.profil)
        zustand = dialogs.feld_bearbeiten(feld, aktuelles)
        self.store.set_dialog(chat_id, zustand.to_dict())
        prompt, kb = views.render_setup_step(feld, zustand.daten)
        self.telegram.send(prompt, chat_id=chat_id, keyboard=kb)

    # ── Callback-Queries (Inline-Buttons) ───────────────────────────────

    def _callback(self, cq: dict) -> None:
        chat_id = str(cq["message"]["chat"]["id"])
        data = cq.get("data", "")
        self.telegram.answer_callback_query(cq["id"])

        if data.startswith(("radtyp:", "radius:", "schwelle:")):
            self._dialog_eingabe(chat_id, self.store.get_dialog(chat_id), data, ist_callback=True)
            return
        if data.startswith("edit:"):
            self._starte_einzelfeld(chat_id, data.split(":", 1)[1])
            return
        if data == "reset:fragen":
            text_, kb = views.render_reset_bestaetigung()
            self.telegram.send(text_, chat_id=chat_id, keyboard=kb)
            return
        if data == "reset:ja":
            self.store.reset_profil()
            self.telegram.send("Profil wurde auf Standardwerte zurueckgesetzt.", chat_id=chat_id)
            return
        if data == "reset:nein":
            self.telegram.send("Abgebrochen — Profil unveraendert.", chat_id=chat_id)
            return
        if data == "blockliste:zeigen":
            text_, kb = views.render_blockliste(self.store.blockliste_view())
            self.telegram.send(text_, chat_id=chat_id, keyboard=kb or None)
            return
        if data.startswith("blockliste:verkaeufer_entsperren:"):
            name = data.split(":", 2)[2]
            self.store.unblock_seller(name)
            self.telegram.send(f"Verkaeufer '{html.escape(name)}' wieder freigegeben.", chat_id=chat_id)
            return
        if data.startswith("blockliste:verkaeufer_sperren:"):
            name = data.split(":", 2)[2]
            self.store.block_seller(name)
            text_ = f"🚫 Verkaeufer '{html.escape(name)}' blockiert — wird nicht mehr gemeldet."
            self.telegram.send(text_, chat_id=chat_id)
            return
        if data.startswith("blockliste:inserat_entsperren:"):
            key = data.split(":", 2)[2]
            self.store.unblock_listing(key)
            self.telegram.send("Inserat wieder freigegeben.", chat_id=chat_id)
            return
        if data.startswith("blockliste:inserat_sperren:"):
            key = data.split(":", 2)[2]
            entry = self.store.get(key)
            if entry:
                self.store.block_listing(key, entry["title"], entry["url"], reason="manuell blockiert")
                self.telegram.send("🚫 Inserat blockiert — wird nicht mehr gemeldet.", chat_id=chat_id)
            return
        if data.startswith("merkliste:hinzufuegen:"):
            key = data.split(":", 2)[2]
            entry = self.store.get(key)
            if entry:
                self.store.merkliste_add_key(key, entry["title"], entry["url"])
                self.telegram.send("🔖 Zur Merkliste hinzugefuegt.", chat_id=chat_id)
            return
        if data.startswith("merkliste:entfernen:"):
            key = data.split(":", 2)[2]
            self.store.merkliste_remove(key)
            self.telegram.send("Von der Merkliste entfernt.", chat_id=chat_id)
            return

    # ── Dialog-Zustandsmaschine ─────────────────────────────────────────

    def _dialog_eingabe(self, chat_id: str, dialog_dict: dict | None, wert: str, ist_callback: bool) -> None:
        if dialog_dict is None:
            return
        zustand = dialogs.DialogZustand.from_dict(dialog_dict)
        schritt = zustand.schritt
        fehler: str | None = None

        if schritt == dialogs.RADTYP:
            # "weiter"/"fertig" als Text zaehlt genauso wie der Button-Tap
            # auf "Weiter →" — wer das tippt statt zu tippen (im Sinne von
            # antippen), soll trotzdem vorankommen.
            ist_weiter = (ist_callback and wert == "radtyp:weiter") or (
                not ist_callback and wert.strip().lower() in ("weiter", "fertig", "ok", "los")
            )
            if ist_weiter:
                if not zustand.daten.get("radtypen"):
                    fehler = "Bitte zuerst mindestens einen Radtyp antippen (Buttons oben), dann 'weiter'."
                else:
                    self._schritt_weiter(chat_id, zustand)
                    return
            elif ist_callback:
                radtyp = wert.split(":", 1)[1]
                zustand.daten["radtypen"] = dialogs.toggle_radtyp(zustand.daten.get("radtypen", []), radtyp)
                self.store.set_dialog(chat_id, zustand.to_dict())
                prompt, kb = views.render_setup_step(schritt, zustand.daten)
                self.telegram.send(prompt, chat_id=chat_id, keyboard=kb)
                return
            else:
                fehler = (
                    "Bitte die Buttons oben antippen, um Radtypen auszuwaehlen — "
                    "dann 'weiter' tippen oder schreiben."
                )

        elif schritt == dialogs.STANDORT:
            plz, fehler = dialogs.parse_plz(wert)
            if plz:
                zustand.daten["standort"] = plz

        elif schritt == dialogs.RADIUS:
            roh = wert.split(":", 1)[1] if ist_callback else wert
            radius, fehler = dialogs.parse_radius(roh)
            if radius:
                zustand.daten["radius"] = radius

        elif schritt == dialogs.PREISRAHMEN:
            rahmen, fehler = dialogs.parse_preisrahmen(wert)
            if rahmen:
                zustand.daten["preisrahmen"] = list(rahmen)

        elif schritt == dialogs.SCHWELLE:
            roh = wert.split(":", 1)[1] if ist_callback else wert
            prozent, fehler = dialogs.parse_prozent(roh)
            if prozent:
                zustand.daten["schwelle"] = prozent

        elif schritt == dialogs.ZEITEN:
            zeiten, fehler = dialogs.parse_zeiten(wert)
            if zeiten:
                zustand.daten["zeiten"] = zeiten

        if fehler:
            self.telegram.send(fehler, chat_id=chat_id)
            return

        self._schritt_weiter(chat_id, zustand)

    def _schritt_weiter(self, chat_id: str, zustand: dialogs.DialogZustand) -> None:
        if zustand.flow == "edit":
            self._dialog_abschliessen(chat_id, zustand)
            return
        naechster = dialogs.naechster_schritt(zustand.schritt)
        if naechster is None:
            self._dialog_abschliessen(chat_id, zustand)
            return
        zustand.schritt = naechster
        self.store.set_dialog(chat_id, zustand.to_dict())
        prompt, kb = views.render_setup_step(naechster, zustand.daten)
        self.telegram.send(prompt, chat_id=chat_id, keyboard=kb)

    def _dialog_abschliessen(self, chat_id: str, zustand: dialogs.DialogZustand) -> None:
        profil = self.store.profil
        daten = zustand.daten

        if daten.get("radtypen"):
            profil.radtypen = daten["radtypen"]
        if daten.get("standort"):
            profil.home_plz = daten["standort"]
            geocoder = Geocoder(self.http, self.store.data["geo"], profil.home_lat, profil.home_lon)
            koordinaten = geocoder.resolve(profil.home_plz)
            if koordinaten:
                profil.home_lat, profil.home_lon = koordinaten
        if daten.get("radius"):
            profil.max_distance_km = int(daten["radius"])
        if daten.get("preisrahmen"):
            profil.min_price_eur, profil.max_price_eur = daten["preisrahmen"]
        if daten.get("schwelle"):
            profil.min_discount_pct = daten["schwelle"]
        if daten.get("zeiten"):
            profil.digest_times = daten["zeiten"]

        profil.validate_radtypen()
        self.store.set_profil(profil)
        self.store.clear_dialog(chat_id)

        if zustand.flow == "edit":
            self.telegram.send("Gespeichert.", chat_id=chat_id)
            self._zeige_profil(chat_id)
        else:
            text_ = "✅ Setup abgeschlossen! Mit /profil kannst du es dir jederzeit ansehen."
            self.telegram.send(text_, chat_id=chat_id)

    # ── Anzeigen, die den Store lesen ────────────────────────────────────

    def _zeige_profil(self, chat_id: str) -> None:
        profil = self.store.profil

        def passt_zum_profil(entry: dict) -> bool:
            preis = entry.get("prices", [[None, None]])[-1][1]
            return preis is not None and profil.min_price_eur <= preis <= profil.max_price_eur

        passende, neue = self.store.treffer_stats(passt_zum_profil)
        quellen_status = [(q.name, q.aktiv(), q.inaktiv_grund()) for q in self.quellen]
        text_, kb = views.render_profil(profil, passende, neue, quellen_status)
        self.telegram.send(text_, chat_id=chat_id, keyboard=kb)

    def _zeige_markt(self, chat_id: str) -> None:
        import statistics

        model_keys = set(self.store.data["market"]) | set(self.store.data["neupreise"])
        zeilen = []
        for model_key in model_keys:
            markt = self.store.market_samples(model_key)
            neu = self.store.neupreis_samples(model_key)
            zeilen.append(
                (
                    model_key,
                    statistics.median(markt) if markt else None,
                    statistics.median(neu) if neu else None,
                    len(markt) + len(neu),
                )
            )
        self.telegram.send(views.render_markt(zeilen), chat_id=chat_id)

    def _freitextsuche(self, chat_id: str, query: str) -> None:
        from gravelbot.enrich.attributes import apply_attributes
        from gravelbot.scoring.filters import passes_filters

        self.telegram.send(views.render_suche_laeuft(query), chat_id=chat_id)
        treffer = volltextsuche_alle(
            self.quellen,
            query,
            max_seiten=self.settings.suche_max_seiten_pro_quelle,
            gesamtlimit=self.settings.suche_gesamtlimit,
        )
        profil = self.store.profil
        passend = [
            t
            for t in treffer
            if passes_filters(t, profil)
            and not self.store.is_listing_blocked(t.key)
            and not self.store.is_seller_blocked(t.seller_name)
        ]
        passend.sort(key=lambda t: t.price_eur)
        if not passend:
            self.telegram.send("Keine Treffer im Preisrahmen des Profils gefunden.", chat_id=chat_id)
            return
        for listing in passend[:8]:
            apply_attributes(listing)
            keyboard = views.render_deal_keyboard(listing.key, listing.seller_name)
            self.store.record(listing)
            self.telegram.send(views.render_deal_freitext(listing), chat_id=chat_id, keyboard=keyboard)
        if len(passend) > 8:
            self.telegram.send(f"… und {len(passend) - 8} weitere Treffer.", chat_id=chat_id, preview=False)


def _profil_als_dialogdaten(profil: Profil) -> dict:
    return {
        "radtypen": list(profil.radtypen),
        "standort": profil.home_plz,
        "radius": profil.max_distance_km,
        "preisrahmen": [profil.min_price_eur, profil.max_price_eur],
        "schwelle": profil.min_discount_pct,
        "zeiten": list(profil.digest_times),
    }
