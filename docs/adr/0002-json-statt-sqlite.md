# 0002 — state.json statt SQLite

## Status

Akzeptiert (Fortführung der ursprünglichen Entscheidung aus Phase 0).

## Kontext

Der Bot muss sich Preishistorien, Marktdaten, Profil, Merkliste, Blockliste
und den Telegram-Offset zwischen GitHub-Actions-Läufen merken. Der Lauf
selbst ist zustandslos (frischer Container alle 30 Minuten); Persistenz
muss über den Lauf hinweg im Git-Repo landen, weil es keine externe
Datenbank und keinen Dauerprozess gibt.

## Entscheidung

Der komplette Zustand bleibt eine einzelne JSON-Datei (`state.json`), die
am Ende jedes Laufs zurück ins Repo committet wird.

## Begründung

- **Keine Infrastruktur nötig.** SQLite bräuchte eine Binärdatei, die sich
  in Git schlecht diffen lässt und bei parallelen Läufen (siehe
  `concurrency`-Guard in `scan.yml`) Merge-Konflikte praktisch unlesbar
  macht. JSON mit `sort_keys=True` erzeugt stabile, lesbare Diffs.
- **Transparenz.** Der Repo-Besitzer kann `state.json` direkt in der
  GitHub-Weboberfläche öffnen und nachvollziehen, was der Bot weiß —
  wichtig, da er auch vom Handy aus mit dem Projekt arbeitet.
- **Datenmenge ist klein genug.** Ein paar hundert Inserate mit
  Preishistorie plus Marktdaten sind einige hundert KB, kein
  Performance-Thema.
- **Kein Nebenläufigkeits-Problem, das eine echte DB lösen würde** — es
  läuft ohnehin nur ein Job gleichzeitig (Concurrency-Group in
  `scan.yml`).

## Konsequenzen

- Migrationen sind reine JSON-Transformationen (`storage/migrations.py`),
  keine Schema-Migrationen im DB-Sinn.
- Wächst der Datenbestand deutlich (mehrere Zehntausend Inserate), wird
  diese Entscheidung neu bewertet werden müssen.
