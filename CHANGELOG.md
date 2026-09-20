# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionsnummern folgen keinem strengen Semver-Schema (Ein-Personen-Projekt,
läuft direkt von `main`).

## [0.2.2] — Code-Review-Haerten: Robustheit, Korrektheit, Testabdeckung

Ein systematischer Review-Durchgang durch den kompletten `gravelbot`-Code
nach dem Webhook-Debugging, mit dem Ziel: keine stillen Datenverluste,
keine unnoetigen Abstuerze, keine unreachable Dead Ends. Kein neues
Feature, ausser wo eine bestehende, halb verdrahtete Infrastruktur
(Verkaeufer-Blockliste) vervollstaendigt statt entfernt wurde.

### Behoben

- **state.json war nicht crash-sicher**: `Store.save()` schrieb direkt in
  die Zieldatei — ein Absturz mitten im Schreiben haette eine kaputte,
  nicht mehr ladbare Datei hinterlassen. Jetzt: Temp-Datei + atomarer
  `os.replace()`.
- **`is_first_run` konnte nach langer Pause faelschlich wieder anspringen**:
  wurde aus "keine Listings vorhanden" abgeleitet — nach dem Pruning
  (45 Tage) waere das bei einem lange pausierten Profil wieder wahr
  geworden und haette einen Lauf lang echte Deals stumm geschluckt. Jetzt
  ein eigenes, persistentes Flag.
- **Freitextsuche (`/suche`) war bei Leerzeichen/Sonderzeichen kaputt**:
  weder `bikemarkt.volltext()` noch `buycycle.volltext()` noch
  `ebay._search_raw()` haben die Query URL-kodiert — ein Wort wie "Canyon
  Grizl" haette die Anfrage-URL zerstoert. Behoben mit `urllib.parse.quote`.
- **Bikemarkt-Volltextsuche paginierte nie wirklich**: `?page=2` auf der
  urspruenglichen Such-URL liefert (gegen die echte Seite verifiziert)
  wieder Seite 1 — Pagination funktioniert nur auf der Redirect-Ziel-URL.
- **Callback-Data konnte Telegrams 64-Byte-Limit sprengen**: ein langer
  eBay-Verkaeufername oder Listing-Key im Button haette nicht nur den
  Button, sondern das Senden der GESAMTEN Nachricht scheitern lassen.
  Neuer `_safe_cb()`-Helfer kappt sicher.
- **Router stuerzte bei leerer Nachricht ab** (`"".split()` entpackt zu
  `[]`, `cmd, *rest = []` wirft `ValueError`).
- **`/suche <text>` escapte die Nutzereingabe nicht** — ein `&` oder `<` im
  Suchbegriff haette die HTML-Nachricht fuer Telegram ungueltig gemacht.
- **Verkaeufer-Blockliste war unvollstaendig verdrahtet**: `block_seller()`
  hatte keinen einzigen Aufrufer, und selbst ein geblockter Verkaeufer
  wurde beim Scan nie tatsaechlich rausgefiltert. Jetzt: `Listing.
  seller_name` (aus eBay befuellt), ein "Verkaeufer blocken"-Button an
  jedem eBay-Deal, und ein echter Filter im Scan-Lauf.
- **Geocoder cachte Netzwerkfehler wie einen echten Negativbefund**: ein
  einmaliger Timeout haette eine PLZ dauerhaft von der Standort-Aufloesung
  ausgeschlossen. Jetzt wird nur eine echte "kein Ort gefunden"-Antwort
  gecacht, kein `None` von `Http.get()`.
- **`Http.get()` stuerzte bei einem `Retry-After`-Header im Datumsformat
  ab** (RFC 7231 erlaubt neben Sekunden auch ein HTTP-Datum; blankes
  `int()` darauf wirft `ValueError`).
- **Digest-Nachrichten konnten Telegrams 4096-Zeichen-Limit sprengen**:
  fester Deckel von 20 Eintraegen pro Nachricht statt tatsaechlicher
  Zeichenlaenge. Jetzt laengenbasiert gechunkt.
- **`parse_preisrahmen`-Regex war ein Zeichensatz-Bug**: `[-–bis]+` matcht
  jedes einzelne Zeichen '-','–','b','i','s' statt des Worts "bis" — z.B.
  haette "500 sbi 3500" faelschlich funktioniert.
- `HOME_LAT`/`HOME_LON`-Environment-Variablen waren toter Code — nirgends
  gelesen, seit der Standort ins Profil gewandert ist. Entfernt.
- Digest-Puffer wuchs unbegrenzt, wenn er nie geleert wird (z.B. kaputte
  `digest_times`) — jetzt auf 200 Eintraege gedeckelt.
- Migration verliess sich auf `setdefault("blockliste", ...)`, das bei
  einer nur teilweise vorhandenen Blockliste (z.B. von Hand editiert)
  nicht mehr greift — Unterschluessel jetzt einzeln abgesichert.
- Laufzusammenfassung zeigte bei stillen Laeufen "gemeldete Deals", obwohl
  nichts verschickt wurde — jetzt getrennt: "gefunden" vs. "tatsaechlich
  gemeldet".
- Toter Code entfernt: `Telegram.edit_message()` (nie aufgerufen).

### Hinzugefügt

- ~50 neue Tests fuer die obigen Fixes plus bisher komplett ungetestete
  Module (`telegram/views.py`, `enrich/geocode.py`, `http.py`).

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
