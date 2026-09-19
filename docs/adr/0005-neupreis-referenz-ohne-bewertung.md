# 0005 — Neupreis-Referenz sammeln, aber noch nicht bewerten

## Status

Akzeptiert für Phase 1. Bewusst unvollständig — Fortsetzung geplant.

## Kontext

Neuware-Quellen (Canyon Outlet, Rose Sale, Bike-Components) liefern nicht
nur einen Preis, sondern auch einen Streichpreis/UVP
(`Listing.list_price_eur`, `Listing.discount_vs_list_pct`). Die bestehende
Deal-Erkennung (`scoring/evaluate.py`) bewertet Angebote ausschließlich
gegen den Median der eigenen Gebrauchtmarkt-Preishistorie je Modell
(`market`-Samples in `state.json`).

## Entscheidung

Neupreise werden gesammelt (`Store.add_neupreis_sample`,
`state["neupreise"]`) und in `/markt` angezeigt, fließen aber in Phase 1
**nicht** in die Deal-Bewertung ein. Ein Neuware-Angebot wird nur dann als
Deal gemeldet, wenn es zufällig auch den bestehenden
Gebrauchtmarkt-Median unterschreitet.

## Begründung

- Die vorhandene Bewertungslogik ist auf Gebrauchtmarkt-Preisschwankungen
  zugeschnitten (Median über die letzten Beobachtungen). Neupreise
  brauchen eine eigene Definition von "Deal" (z. B. "Rabatt größer als X %
  UND größer als der historische Bestrabatt für dieses Modell"), die neu
  durchdacht werden muss statt sie hastig in die bestehende Funktion zu
  pressen.
- Sauberer, in sich abgeschlossener Schnitt: Diese Phase liefert
  verlässlich gesammelte Rohdaten; die nächste baut die Bewertung
  darauf auf, mit echten historischen Neupreis-Daten als Grundlage statt
  mit Tag-1-Annahmen ohne jede Datenbasis.

## Konsequenzen

- Nutzer sehen Neupreis-Rabatte vorerst nur passiv in `/markt` und direkt
  am einzelnen Angebot (`Listing.discount_vs_list_pct`), nicht als
  automatische Benachrichtigung.
- Phase 2: eigene Bewertungsregel für Neuware, vermutlich als weiterer
  `reason`-Typ neben `price_drop`/`under_market` in `scoring/evaluate.py`.
