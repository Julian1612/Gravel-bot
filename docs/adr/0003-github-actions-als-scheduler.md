# 0003 — GitHub Actions als Scheduler (statt eigener Server)

## Status

Akzeptiert (Fortführung der ursprünglichen Entscheidung aus Phase 0),
mit Konsequenzen für das Telegram-Interface in Phase 1.

## Kontext

Der Bot braucht einen regelmäßigen Trigger (alle 30 Minuten) und einen Ort,
an dem er läuft. Optionen wären ein eigener Server/VM, ein Cloud-Function-
Dienst oder GitHub Actions mit `schedule`-Trigger.

## Entscheidung

GitHub Actions bleibt der Scheduler; es gibt keinen Dauerprozess.

## Begründung

- Kostenlos im Rahmen der Nutzung eines privaten Projekts.
- Kein Server-Betrieb, keine Patches, keine Uptime-Sorgen.
- Läuft im selben Repo wie der Code — ein Ort für alles.
- `concurrency`-Gruppe verhindert überlappende Läufe.

## Konsequenzen für Phase 1

Diese Entscheidung hat einen direkten Effekt auf das neue interaktive
Telegram-Interface: Es gibt **kein Long-Polling und keinen Webhook** im
klassischen Sinn, weil zwischen zwei Läufen kein Prozess lebt. Der
`/setup`-Dialog (Zustandsmaschine in `telegram/dialogs.py`) funktioniert
deshalb so:

1. Jeder Lauf holt per `getUpdates` alle Nachrichten seit dem zuletzt
   gespeicherten `telegram_offset` (persistiert in `state.json`).
2. Jede Nachricht/jeder Button-Klick treibt den Dialog genau einen Schritt
   weiter; der Zwischenzustand landet in `state.json` (`dialoge`).
3. Antworten kommen sofort innerhalb desselben Laufs — aber der nächste
   Schritt des Nutzers wird erst im nächsten Cron-Lauf verarbeitet.

Ein `/setup`-Durchlauf mit sechs Schritten kann sich dadurch über bis zu
drei Stunden ziehen (sechs Läufe à 30 Minuten), statt über Sekunden wie
bei einem Server mit Webhook. Das ist ein bewusster Kompromiss: ein
eigener Server nur für Sofort-Antworten stünde in keinem Verhältnis zum
Nutzen für ein Ein-Personen-Projekt.

## Alternativen, die verworfen wurden

- **Eigener Server mit Webhook:** würde Hosting-Kosten und -Wartung
  bedeuten, für einen Preisalarm-Bot unverhältnismäßig.
- **Kürzerer Cron-Takt nur für Telegram-Polling:** GitHub Actions hat ein
  Minimum von 5 Minuten für `schedule`-Trigger und keine Garantie für
  exakte Ausführungszeiten — ein deutlich kürzerer Takt würde weder die
  Latenz zuverlässig senken noch zum Scan-Rhythmus passen.
