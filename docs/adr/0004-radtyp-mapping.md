# 0004 — Radtyp-Zuordnung je Quelle

## Status

Akzeptiert.

## Kontext

Das Profil kennt vier Radtypen: Gravel, Endurance-Rennrad, Cyclocross,
Rennrad. Jede Quelle hat aber ihr eigenes, gewachsenes Kategorieschema
(Bikemarkt-Kategorie-IDs, buycycle-Suchbegriffe, Canyon-Outlet-Facetten,
Rose-Sale-Kategorie-IDs, Bike-Components-Kategoriepfade, eBay-Freitext).
Keine der Quellen unterscheidet alle vier Radtypen einzeln.

## Entscheidung

Jede Quelle bekommt in `config.py` eine eigene Zuordnungstabelle
(`BIKEMARKT_CATEGORIES`, `BUYCYCLE_QUERY`, `EBAY_QUERY`,
`CANYON_CATEGORY`, `ROSE_SALE_CATEGORY`, `BIKE_COMPONENTS_CATEGORY_PATH`).
Wo eine Quelle keine eigene Kategorie für Endurance-Rennrad oder
Cyclocross hat, wird auf "Rennrad" (bzw. die gemischte
"Rennrad & Gravel"-Kategorie bei Bikemarkt) ausgewichen — verifiziert
gegen die echten Kategorie-/Filterlisten der jeweiligen Seite, nicht
geraten.

Konkret:

| Quelle | Gravel | Rennrad | Endurance-Rennrad | Cyclocross |
| --- | --- | --- | --- | --- |
| Bikemarkt | Kat. 123 | Kat. 17 + 194 | Kat. 17 + 194 | Kat. 17 + 194 |
| buycycle | Query "gravel" | Query "rennrad" | Query "rennrad" | Query "cyclocross" |
| eBay | "Gravelbike" | "Rennrad" | "Rennrad" | "Cyclocross" |
| Canyon Outlet | Gravel Outlet | Road Outlet | Road Outlet | Road Outlet |
| Rose Sale | Kategorie 1209 | Kategorie 151 | Kategorie 151 | Kategorie 151 |
| Bike-Components | /gravelbike/ | /rennrad/ | /rennrad/ | /rennrad/ |

## Begründung

Eine Quelle künstlich in Unterkategorien aufzuteilen, die sie selbst nicht
kennt, würde bedeuten, mit Keyword-Heuristiken auf Verdacht zu filtern
("cyclocross" im Titel suchen) — das liefert sowohl falsch-positive als
auch falsch-negative Treffer und würde echte Cyclocross-/Endurance-Angebote
verwerfen, die einfach nicht so betitelt sind. Die grobere, aber
verlässliche Zuordnung auf die nächstgrößere reale Kategorie ist ehrlicher
als eine vorgetäuschte Präzision.

## Konsequenzen

- Wer nur "Cyclocross" im Profil auswählt, bekommt von den meisten Quellen
  trotzdem das komplette Rennrad-Sortiment (unscharf, aber vollständig).
- Wird später eine feinere serverseitige Facette bei einer Quelle
  gefunden, kann die jeweilige Zuordnungstabelle unabhängig von den
  anderen verfeinert werden.
