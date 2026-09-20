# 0006 — Telegram-Webhook statt reinem Polling

## Status

Akzeptiert, optional (Standard bleibt Polling — siehe unten).

## Kontext

ADR 0003 (GitHub Actions als Scheduler) hat bewusst in Kauf genommen, dass
der Bot keinen Dauerprozess hat und Telegram-Nachrichten deshalb nur
verarbeitet werden, wenn `scan.yml` sowieso gerade läuft (alle 30 Minuten,
5–21 Uhr UTC). In der Praxis fühlt sich das beim `/setup`-Dialog spürbar
zäh an — Antwortzeiten von mehreren Minuten bis zu mehreren Stunden
(außerhalb des Cron-Fensters).

## Entscheidung

Ein optionaler Telegram-Webhook, realisiert über einen schlanken
Cloudflare Worker (`infra/telegram-webhook/worker.js`), der eingehende
Updates unverändert per `repository_dispatch` an GitHub weiterreicht. Ein
neuer Workflow (`telegram-update.yml`) verarbeitet dann genau dieses eine
Update sofort — typischerweise innerhalb weniger Sekunden statt Minuten.

Der reguläre Scan-Workflow (`scan.yml`) bleibt der einzige Ort, an dem
tatsächlich gescannt wird; der Webhook-Pfad scannt nur, wenn das Update
selbst `/scan` ausgelöst hat (`Router.scan_erzwingen`), damit nicht jede
`/profil`-Anfrage einen kompletten Multi-Quellen-Scan lostritt.

## Begründung

- **Kein eigener Server nötig.** Ein Cloudflare Worker läuft im
  kostenlosen Tarif, ohne Betrieb/Wartung — anders als ein VM-basierter
  Bot mit echtem Long-Polling, was ADR 0003 gerade vermeiden wollte.
- **Der Worker enthält keine Bot-Logik.** Er prüft nur ein
  Secret-Token und reicht das Update weiter. Die komplette
  Ablaufsteuerung bleibt in `gravelbot` — kein Code, der nur auf
  Cloudflare läuft und dort separat gepflegt/getestet werden müsste.
- **Optional, nicht verpflichtend.** Wer den Aufwand (Cloudflare-Account,
  GitHub-Token, Secrets pflegen) nicht will, lässt `TELEGRAM_WEBHOOK_MODE`
  einfach ungesetzt — dann pollt `scan.yml` weiter wie bisher, keine
  Funktionseinbuße, nur langsamer.

## Konsequenzen

- Telegram erlaubt `getUpdates` und Webhook nicht gleichzeitig. Solange
  der Webhook aktiv ist, muss `scan.yml` `TELEGRAM_WEBHOOK_MODE=1`
  gesetzt bekommen (Repository-Variable), sonst würde es bei jedem
  Polling-Versuch nur noch einen Konfliktfehler von Telegram zurückbekommen.
- Ein neues Secret (`GITHUB_TOKEN` für den Worker) existiert jetzt
  außerhalb von GitHub, im Cloudflare-Dashboard. Bei Rotation muss es an
  zwei Stellen aktualisiert werden.
- Fällt der Cloudflare Worker aus (Ausfall, falsches Secret, Kontingent),
  bekommt der Bot gar keine Telegram-Updates mehr, bis das behoben ist —
  es gibt keinen automatischen Rückfall auf Polling, solange
  `TELEGRAM_WEBHOOK_MODE=1` gesetzt ist. Abhilfe: Repo-Variable
  zurücksetzen und `deleteWebhook` aufrufen (siehe
  `docs/telegram-webhook-setup.md`).
