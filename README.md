# Gravel Deal Bot

Durchsucht Gebrauchtmarkt- und Neuware-Quellen nach Renn-/Gravelbikes, merkt
sich Preise, erkennt Schnäppchen und schickt sie per Telegram. Läuft alle
30 Minuten als GitHub Action (`.github/workflows/scan.yml`), es gibt keinen
Dauerprozess und keinen eigenen Server.

## Was ändere ich wo?

Das Projekt ist bewusst so aufgeräumt, dass man auch vom Handy aus (GitHub-
Weboberfläche) den richtigen Ort findet:

| Ich will ... | ... ändere ich hier |
| --- | --- |
| Schwellenwerte für Deals (Standard-Werte) | [`src/gravelbot/models.py`](src/gravelbot/models.py) — `Profil`-Defaults. Laufende Anpassung geht auch per Telegram: `/schwelle` |
| Preisrahmen, Radius, Radtyp (Standard-Werte) | ebenfalls `Profil` in `models.py`. Laufende Anpassung: `/setup` oder `/profil` |
| Eine neue Quelle hinzufügen | neue Datei unter [`src/gravelbot/sources/`](src/gravelbot/sources/) bzw. `sources/shops/`, dann in [`sources/registry.py`](src/gravelbot/sources/registry.py) eintragen |
| Ausschluss-Wörter (Rahmensets, E-Bikes, Teile) | `HARD_EXCLUDE` in [`src/gravelbot/config.py`](src/gravelbot/config.py) |
| Radtyp-Zuordnung je Quelle (Kategorie-IDs) | ebenfalls `config.py` (`BIKEMARKT_CATEGORIES`, `CANYON_CATEGORY`, ...) |
| Telegram-Texte | [`src/gravelbot/telegram/views.py`](src/gravelbot/telegram/views.py) |
| Cron-Zeiten des Laufs | [`.github/workflows/scan.yml`](.github/workflows/scan.yml) |

## Projektstruktur

```
├── bot.py                      # duenner Shim, ruft gravelbot.__main__ auf
├── src/gravelbot/
│   ├── __main__.py             # CLI: --dry-run, --test-telegram, --scan-only
│   ├── app.py                  # Orchestrierung eines Laufs
│   ├── config.py               # Einstellungen aus Env + Defaults
│   ├── models.py               # Listing, Profil, Deal (dataclasses)
│   ├── http.py                 # HTTP-Client mit Rate-Limit und Retries
│   ├── storage/                # state.json laden/speichern, Migrationen
│   ├── sources/                # Bikemarkt, buycycle, eBay, Shops
│   │   └── shops/               # Canyon Outlet, Rose Sale, Bike-Components, ...
│   ├── enrich/                  # Attributextraktion, Geocoding
│   ├── scoring/                 # Filter & Bewertung (reine Funktionen)
│   └── telegram/                 # Client, Router, Dialoge, Views
├── tests/                        # pytest, ausschliesslich offline (Fixtures)
└── docs/adr/                     # kurze Entscheidungsnotizen
```

## Einrichtung

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # Laufzeit- + Test-Abhaengigkeiten
```

Ausfuehren:

```bash
python bot.py --dry-run             # scannen, nichts senden/speichern
python bot.py --test-telegram       # nur eine Testnachricht schicken
python bot.py --register-commands   # Befehlsliste bei Telegram registrieren (einmalig, siehe unten)
python bot.py --scan-only           # Telegram-Befehle ueberspringen, nur scannen
python bot.py                       # normaler Lauf (wie in der Action)
```

Tests, Linting, Typcheck:

```bash
pytest tests/
ruff check .
ruff format --check .
mypy src/gravelbot
```

## Secrets

Im Repo unter *Settings → Secrets and variables → Actions* zu setzen:

| Secret | Pflicht? | Wofuer |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | ja, sonst nur Log-Ausgabe | Bot-Token von [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | ja, sonst nur Log-Ausgabe | Chat-ID, an die gesendet wird |
| `EBAY_CLIENT_ID` | optional | eBay Browse API — ohne Wert wird die Quelle sauber übersprungen |
| `EBAY_CLIENT_SECRET` | optional | eBay Browse API |

### eBay-Credentials besorgen

1. Account anlegen auf https://developer.ebay.com/
2. Im [Developer-Portal](https://developer.ebay.com/my/keys) eine neue App anlegen
3. **Production Keys** erzeugen (nicht Sandbox) — der Bot nutzt den
   Client-Credentials-Flow der Browse API, das geht nur mit Production Keys
4. `Client ID` und `Client Secret` als `EBAY_CLIENT_ID` /
   `EBAY_CLIENT_SECRET` ins Repo eintragen

Der Bot holt sich damit selbst ein OAuth-Token (gültig ~2 Std.); es kommt
ausschließlich zur Laufzeit in den Speicher, nie in `state.json`.

## Telegram-Befehle

| Befehl | Wirkung |
| --- | --- |
| `/start` | Willkommensnachricht, Einstieg für neue Chats |
| `/help` | Zeigt diese Befehlsliste an (auch `hilfe` oder einfach `help` ohne Schrägstrich funktioniert) |
| `/setup` | Suchprofil neu einrichten (Radtyp, Standort, Radius, Preis, Rahmengröße, Schwelle, Digest-Zeiten) |
| `/profil` | Profil ansehen, mit Bearbeiten-Buttons je Zeile, Trefferzahl im Bestand, Quellenstatus |
| `/zeiten` | Digest-Uhrzeiten setzen |
| `/groesse` | Rahmengröße setzen — Körpergröße in cm (z.B. `178`) oder direkt Größen (z.B. `56,58` oder `M,L`); `egal` schaltet den Filter aus |
| `/schwelle` | Deal-Schwelle (% unter Marktwert) setzen |
| `/markt` | Marktpreise & Neupreis-Referenz je Modell |
| `/merkliste` | gemerkte Inserate ansehen/entfernen |
| `/suche <Text>` | Freitextsuche über alle Quellen mit Volltextsuche |
| `/scan` | Lauf sofort anstoßen (läuft im selben Cron-Durchlauf mit) |
| `/pause` | Suche pausieren/fortsetzen |
| `/reset` | Profil auf Standardwerte zurücksetzen (mit Rückfrage) |

Befehle sind tolerant: der Schrägstrich ist optional (`setup` funktioniert
genauso wie `/setup`), und ein angehängter Bot-Username (`/setup@dein_bot`,
wie ihn manche Telegram-Clients automatisch anfügen) wird ignoriert.

**Natives Befehlsmenü:** einmalig im Repo unter *Actions → Gravel Scan →
Run workflow* den Modus **`befehle-registrieren`** auswählen (oder lokal
`python bot.py --register-commands`) — danach zeigt Telegram beim Tippen
von `/` im Chat alle Befehle mit Beschreibung als Menü an, statt dass man
sie auswendig kennen muss. Die Liste kommt aus
[`src/gravelbot/config.py`](src/gravelbot/config.py) (`BOT_COMMANDS`) —
dieselbe Quelle, aus der sich auch `/help` aufbaut, beide können also nie
auseinanderlaufen.

Der Bot läuft nicht als Dauerprozess — ein `/setup`-Dialog zieht sich über
mehrere Cron-Läufe (alle 30 Minuten), nicht über Sekunden. Wer das nicht
abwarten will: [`docs/telegram-webhook-setup.md`](docs/telegram-webhook-setup.md)
richtet einen optionalen Webhook ein, der auf jede Nachricht innerhalb
weniger Sekunden reagiert (siehe auch
[ADR 0006](docs/adr/0006-telegram-webhook.md)).

## Quellen

| Quelle | Art | Status |
| --- | --- | --- |
| Bikemarkt (MTB-News) | gebraucht | aktiv |
| buycycle | gebraucht | aktiv, liefert aber aktuell oft 0 Treffer — buycycle.com blockt automatisierte Anfragen zunehmend per Cloudflare, auch mit ehrlichem User-Agent |
| eBay Browse API | gebraucht, offiziell | aktiv, benötigt `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` |
| Canyon Outlet | neu, Rabatt | aktiv |
| Rose Sale | neu, Rabatt | aktiv |
| Bike-Components (Komplettbike-Kategorien) | neu, Rabatt | aktiv |
| Bike-Discount Sale/B-Ware | neu, Rabatt | **deaktiviert** — Shop antwortet mit HTTP 403 für jeden getesteten User-Agent |
| Bike24 Sale | neu, Rabatt | **deaktiviert** — gleicher Befund wie Bike-Discount |
| fahrrad.de (Gravel/Rennrad/Endurance/Cyclocross-Kollektionen) | neu, Rabatt | aktiv — nutzt das öffentliche Shopify-`products.json`, eine Listing je verfügbarer Rahmengröße |
| Radon-Bikes Outlet | neu, Rabatt | **deaktiviert** — Seite ist eine JS-SPA ohne Produktdaten im Server-HTML |
| Focus-Bikes Outlet | neu, Rabatt | **deaktiviert** — gleicher Befund wie Radon-Bikes Outlet |

Kleinanzeigen wird bewusst nicht unterstützt (Bot-Schutz, AGB-Verbot).

## state.json

Enthält Suchprofil, Inserate mit Preishistorie, Marktpreise und
Neupreis-Referenzen je Modell, Merkliste, Blockliste, Digest-Puffer,
Geo-Cache und den Telegram-Update-Offset. Ein `schema_version`-Feld sorgt
dafür, dass alte Stände beim Laden automatisch migriert werden
(`src/gravelbot/storage/migrations.py`) — nichts geht dabei verloren.
