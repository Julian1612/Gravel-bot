# 0007 — Rennbedingungen im /setup-Dialog: Ursache und Gegenmaßnahmen

## Status

Akzeptiert. Reduziert das Problem erheblich, löst es aber nicht
vollständig — siehe "Verbleibendes Risiko" unten.

## Kontext

Nutzer meldeten, die Radtyp-Mehrfachauswahl in `/setup` sei "super buggy":
mehrere fast identische Nachrichten stapelten sich, jede mit einem
anderen, eingefrorenen Auswahl-Stand, und ein "Weiter"-Tap behauptete
teilweise "kein Radtyp ausgewählt", obwohl sichtbar mehrere Häkchen
gesetzt waren.

Ursache, in Kombination:

1. **Kein In-Place-Edit.** Jeder Button-Tap schickte bisher eine komplett
   neue Nachricht statt die bestehende zu ändern. Mehrere Taps kurz
   hintereinander erzeugten dadurch einen wachsenden Stapel fast
   identischer Nachrichten.
2. **GitHub Actions' `concurrency`-Gruppen sind zum Verwerfen gebaut, nicht
   zum Warten.** `telegram-update.yml` teilte sich mit `scan.yml` die
   Gruppe `gravel-scan`. Laut GitHub-Dokumentation gilt dabei: läuft
   bereits ein Job dieser Gruppe und ein zweiter wird eingereiht
   ("pending"), und kommt währenddessen ein DRITTER dazu, wird der
   zweite (noch nicht gestartete) **verworfen** — nicht etwa in eine
   Warteschlange gestellt. Bei mehreren Taps innerhalb der ~15–25
   Sekunden, die ein GitHub-Actions-Lauf allein für Checkout + Setup +
   Ausführung + Commit + Push braucht, wurden dadurch reihenweise Taps
   nie verarbeitet — sie kamen als `repository_dispatch`-Event an, ihr
   Workflow-Lauf wurde aber nie gestartet.
3. Ein Tap, der doch verarbeitet wurde, aber dabei auf einen **veralteten**
   Checkout-Stand traf (weil sein eigentlicher Vorgänger noch nicht
   gepusht hatte), sah eine ältere Version von `radtypen` als die zuletzt
   sichtbare — daher das "0 ausgewählt trotz sichtbarer Häkchen".

## Entscheidung

Vier Maßnahmen, keine davon für sich allein ausreichend, zusammen aber
wirksam:

1. **In-Place-Edit statt neuer Nachricht** (`Telegram.edit_message()`,
   `Router._antworten()`): jeder Button-Tap in einem Dialogschritt ändert
   dieselbe Nachricht, statt eine neue zu schicken. Macht das Problem
   sichtbar korrekt, auch wenn im Hintergrund noch Läufe verworfen würden.
2. **Die komplette Radtyp-Auswahl als ein Text möglich** (`gravel,
   rennrad`, `dialogs.parse_radtypen`): ein einziger Text-Roundtrip statt
   vier Button-Taps — umgeht das Race komplett für alle, die stattdessen
   tippen. Das ist der eigentlich robuste Weg, nicht nur ein Pflaster.
3. **Eigene `concurrency`-Gruppe pro Telegram-Update**
   (`gravel-telegram-<update_id>` statt der geteilten `gravel-scan`): kein
   Tap wird mehr verworfen, weil ein anderer Tap dazwischenkam — jeder
   bekommt garantiert einen eigenen Lauf.
4. **Retry-Schleife beim `git push`** in beiden Workflows: da mehrere
   Updates jetzt parallel laufen können, muss das Schreiben von
   `state.json` mit Konflikten rechnen. Bis zu 5 Versuche mit
   Zufalls-Backoff statt einem einzigen `git pull --rebase && git push`.

## Verbleibendes Risiko

Diese Kombination macht Datenverlust durch Taps sehr unwahrscheinlich,
aber nicht unmöglich: verändern zwei wirklich gleichzeitig laufende
Läufe exakt dasselbe Feld in `state.json` (z. B. zwei Radtyp-Toggles
innerhalb von Millisekunden), kann der `git rebase` einen echten
Text-Konflikt bekommen, den keiner der 5 Retry-Versuche automatisch
auflösen kann — der zweite Lauf würde dann mit `::error::` fehlschlagen,
sichtbar im Actions-Log, aber der zugehörige Tap ginge verloren. Für
einen von einer Person bedienten Bot ist das realistisch selten (erfordert
zwei Taps innerhalb desselben sehr kurzen Fensters), aber nicht
ausgeschlossen. Die Text-Eingabe (Punkt 2) bleibt der zuverlässigste Weg
für die Radtyp-Auswahl, wenn absolute Verlässlichkeit wichtiger ist als
Buttons.

Eine vollständige Lösung (z. B. echte Zustandsverwaltung über Cloudflare
KV statt Git-Commits als Datenbank) wäre ein deutlich größerer
Architektur-Umbau — siehe ADR 0002 für die Begründung, warum bisher
bewusst bei git+JSON geblieben wurde.
