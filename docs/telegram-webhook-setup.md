# Telegram-Webhook einrichten (schnellere Antworten)

Ohne diese Einrichtung reagiert der Bot nur, wenn `scan.yml` sowieso
gerade läuft (alle 30 Minuten, 5–21 Uhr UTC). Mit dieser Einrichtung
reagiert er innerhalb weniger Sekunden auf jede Nachricht — Hintergrund
dazu in [`docs/adr/0006-telegram-webhook.md`](adr/0006-telegram-webhook.md).

Es kommt eine neue, externe Komponente dazu: ein winziger
[Cloudflare Worker](https://workers.cloudflare.com/) (kostenloser Tarif
reicht locker), der Telegram-Updates entgegennimmt und sofort einen
GitHub-Actions-Lauf anstößt. Der Worker selbst enthält keine Bot-Logik —
nur Weiterleitung.

## 1. GitHub Personal Access Token erzeugen

*Settings → Developer settings → Personal access tokens → Fine-grained
tokens → Generate new token*

- Repository access: nur `Gravel-bot` auswählen
- Permissions: **Contents** → Read and write, **Actions** → Read and
  write, **Metadata** → Read-only (wird automatisch mit ausgewählt)
- Ablaufdatum nach Belieben (bei Ablauf einfach neuen Token erzeugen und
  im Worker-Secret ersetzen)

Token kopieren — wird gleich als Worker-Secret gebraucht, nicht ins Repo
eintragen.

## 2. Cloudflare Worker anlegen

1. Kostenlosen Account auf [dash.cloudflare.com](https://dash.cloudflare.com/) anlegen (falls noch keiner existiert)
2. *Workers & Pages → Create → Create Worker*, einen Namen geben (z. B. `gravel-bot-telegram-webhook`)
3. Im Editor den kompletten Inhalt von [`infra/telegram-webhook/worker.js`](../infra/telegram-webhook/worker.js) einfügen, *Deploy* klicken
4. Unter *Settings → Variables and Secrets* vier **Secrets** anlegen (nicht "Variables" — Secrets werden verschlüsselt gespeichert):
   - `TELEGRAM_WEBHOOK_SECRET` — ein selbst ausgedachter zufälliger String, z. B. mit `openssl rand -hex 32` erzeugt
   - `GITHUB_TOKEN` — der Token aus Schritt 1
   - `GITHUB_OWNER` — `Julian1612`
   - `GITHUB_REPO` — `Gravel-bot`
5. Die Worker-URL notieren (steht oben auf der Worker-Seite, Format `https://gravel-bot-telegram-webhook.<dein-account>.workers.dev`)

Alternativ per CLI (`npm install -g wrangler`, dann `wrangler login`):
im Ordner `infra/telegram-webhook/` `wrangler secret put <NAME>` für jedes
der vier Secrets ausführen und mit `wrangler deploy` deployen.

## 3. Telegram-Webhook registrieren

Einmalig folgenden Aufruf machen (Token und Werte ersetzen), z. B. im
Terminal:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://gravel-bot-telegram-webhook.<dein-account>.workers.dev",
    "secret_token": "<derselbe Wert wie TELEGRAM_WEBHOOK_SECRET>"
  }'
```

Die Antwort sollte `{"ok":true,"result":true,...}` sein. Prüfen, ob es
angekommen ist:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

## 4. Repo-Variable setzen

*Settings → Secrets and variables → Actions → Variables (Tab, nicht
Secrets!) → New repository variable*

- Name: `TELEGRAM_WEBHOOK_MODE`
- Wert: `1`

Das sagt `scan.yml`, nicht mehr per `getUpdates` zu pollen — Telegram
erlaubt Webhook und Polling nicht gleichzeitig, sonst würde `scan.yml`
ab jetzt nur noch Fehler loggen (harmlos, aber unnötig).

## 5. Testen

Dem Bot in Telegram `/profil` schicken. Antwort sollte innerhalb weniger
Sekunden kommen (statt bis zu 30 Minuten). Falls nicht:

- *Actions*-Tab prüfen: taucht ein neuer Lauf des Workflows
  **Telegram Update** auf? Wenn nein → der Worker hat den Dispatch nicht
  ausgelöst (Cloudflare-Worker-Logs im Dashboard unter *Logs* prüfen,
  meist ein falscher `GITHUB_TOKEN` oder falscher `GITHUB_OWNER`/`GITHUB_REPO`)
- Läuft der Workflow, schlägt aber fehl? → Logs des Laufs ansehen, meist
  fehlende/falsche `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`-Secrets

## Rückgängig machen

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook"
```

und die Repo-Variable `TELEGRAM_WEBHOOK_MODE` wieder löschen oder auf
einen leeren Wert setzen — danach pollt `scan.yml` wieder ganz normal wie
vorher.
