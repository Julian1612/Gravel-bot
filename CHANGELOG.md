# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionsnummern folgen keinem strengen Semver-Schema (Ein-Personen-Projekt,
läuft direkt von `main`).

## [0.2.1] — Autorisierung, eBay-Secrets, optionaler Webhook

### Behoben

- **Sicherheitslücke:** der Telegram-Router prüfte nicht, von wem eine
  Nachricht kam — jeder Telegram-Nutzer, der den Bot-Usernamen kannte,
  konnte `/setup`, `/reset`, `/pause` etc. auslösen. Jetzt wird jede
  Nachricht/jeder Button-Klick gegen `TELEGRAM_CHAT_ID` geprüft.
- `scan.yml` reichte `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` nicht an den
  Prozess durch — die eBay-Quelle wäre live immer übersprungen worden,
  egal ob die Secrets gesetzt sind.

### Hinzugefügt

- Optionaler Telegram-Webhook (Cloudflare Worker +
  `repository_dispatch`) für Antworten in Sekunden statt bis zu
  30 Minuten — siehe `docs/telegram-webhook-setup.md` und
  `docs/adr/0006-telegram-webhook.md`. Standardverhalten (Polling)
  bleibt unverändert, wenn nicht eingerichtet.
- Neuer CLI-Modus `--telegram-update` verarbeitet ein einzelnes,
  bereits vorliegendes Update sofort (für den Webhook-Pfad).

## [0.2.0] — Phase 1: mehr Quellen

### Hinzugefügt

- Paketstruktur unter `src/gravelbot/` (vorher: eine `bot.py`-Datei)
- Quellen-Interface (`sources/base.py`, `Quelle`-Protocol) mit
  fehlertoleranter Registrierung (`sources/registry.py`)
- Neue Quelle: eBay Browse API (OAuth Client-Credentials-Flow, überspringt
  sich sauber ohne `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET`)
- Neue Quellen für Neuware mit Rabatt: Canyon Outlet, Rose Sale,
  Bike-Components (Komplettbike-Kategorien)
- Neupreis-Referenz je Modell wird gesammelt und in `/markt` angezeigt
- Radtyp ist jetzt ein Profilfeld (Gravel, Endurance-Rennrad, Cyclocross,
  Rennrad) statt fest verdrahtet, abgefragt im `/setup`-Dialog
- Vollständige interaktive Telegram-Oberfläche: `/setup`-Zustandsmaschine,
  `/profil` mit Bearbeiten-Buttons je Zeile, Trefferzahl und Quellenstatus,
  `/zeiten`, `/schwelle`, `/markt`, `/merkliste`, `/suche`, `/scan`,
  `/pause`, `/reset` mit Bestätigung, Blockliste einsehbar/rückgängig machbar
- Freitextsuche fragt jetzt alle Quellen mit eigener Volltextsuche ab,
  gedeckelt über Seiten- und Gesamtlimit
- Attributextraktion (Rahmengröße, Baujahr, Material, Schaltgruppe, 1x/2x)
  als reine Funktionen in `enrich/attributes.py`
- `schema_version` in `state.json` plus versionierte Migrationen
  (`storage/migrations.py`)
- Laufzusammenfassung je Quelle in `$GITHUB_STEP_SUMMARY`
- Test-Suite (`pytest`, ausschließlich offline über Fixtures) und
  `.github/workflows/test.yml`
- `ruff` (Lint + Format) und `mypy` in CI

### Bekannte Einschränkungen

- Bike-Discount und Bike24 bleiben deaktiviert — beide Shops antworten mit
  HTTP 403 für jeden getesteten User-Agent (Browser wie ehrlicher Bot-UA)
- buycycle liefert seit einiger Zeit oft 0 Treffer — der Shop hinter
  Cloudflare blockt zunehmend auch normale Anfragen; bestehendes Verhalten
  unverändert übernommen, nicht neu kaputt gemacht
- Bikemarkt/buycycle haben keine eigenen Kategorien für Endurance-Rennrad
  und Cyclocross — beide werden dort auf "Rennrad" abgebildet (siehe
  `docs/adr/0004-radtyp-mapping.md`)

## [0.1.0] — Ursprünglicher Stand

- Ein-Datei-Skript (`bot.py`), Bikemarkt + buycycle, feste Modulkonstanten
  für alle Einstellungen, reine Sende-Telegram-Integration ohne Befehle
