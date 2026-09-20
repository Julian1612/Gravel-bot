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
- Permissions: **Contents** → Read and write (das ist die einzige
  tatsächlich benötigte Berechtigung für den `/dispatches`-Endpunkt —
  bestätigt über den Response-Header `x-accepted-github-permissions:
  contents=write`; "Actions" braucht es dafür nicht)
- Ablaufdatum nach Belieben (bei Ablauf einfach neuen Token erzeugen und
  im Worker-Secret ersetzen)

Token kopieren — wird gleich als Worker-Secret gebraucht, nicht ins Repo
eintragen.

## 2. Cloudflare Worker anlegen (Git-Integration)

1. Kostenlosen Account auf [dash.cloudflare.com](https://dash.cloudflare.com/) anlegen (falls noch keiner existiert)
2. *Workers & Pages → Create application → Connect to Git*, das Repo
   `Julian1612/Gravel-bot` auswählen
3. Build-Konfiguration:
   - **Build command**: leer lassen
   - **Deploy command**: `npx wrangler deploy`
   - **Root directory**: `infra/telegram-webhook` (wichtig! liegt nicht im
     Repo-Root — sonst versucht Cloudflare, das Python-Projekt im Root zu
     bauen und scheitert)
   - **Protect with Cloudflare Access**: **ausgeschaltet lassen** — sonst
     kann Telegram den Worker nicht erreichen
4. *Deploy* — der erste Build läuft ohne Secrets durch (Worker antwortet
   danach erstmal mit 401 auf alles, das ist normal, siehe Schritt 4)
5. Unter *Settings → Variables and Secrets* zwei **Secrets** anlegen
   (Typ "Secret", nicht "Variable" — Secrets werden verschlüsselt
   gespeichert und überleben, anders als unverschlüsselte Variables,
   künftige Git-Deploys unverändert):
   - `TELEGRAM_WEBHOOK_SECRET` — ein selbst ausgedachter zufälliger String, z. B. mit `openssl rand -hex 32` erzeugt
   - `GITHUB_TOKEN` — der Token aus Schritt 1
6. Die Worker-URL notieren (Tab *Overview*, Format `https://gravel-bot.<dein-account>.workers.dev`)

`GITHUB_OWNER`/`GITHUB_REPO` müssen **nicht** im Dashboard gesetzt werden —
die stehen schon fest in [`infra/telegram-webhook/wrangler.toml`](../infra/telegram-webhook/wrangler.toml)
(`[vars]`-Block). Das ist bewusst so: unverschlüsselte "Variables", die nur
im Dashboard gesetzt werden, wirft Cloudflare bei jedem Git-Deploy wieder
raus, weil es sie mit der `wrangler.toml` abgleicht — das hat uns beim
Einrichten eine Weile gekostet. Secrets sind davon nicht betroffen.

Alternativ per CLI (`npm install -g wrangler`, dann `wrangler login`):
im Ordner `infra/telegram-webhook/` `wrangler secret put TELEGRAM_WEBHOOK_SECRET`
und `wrangler secret put GITHUB_TOKEN` ausführen, dann `wrangler deploy`.

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
