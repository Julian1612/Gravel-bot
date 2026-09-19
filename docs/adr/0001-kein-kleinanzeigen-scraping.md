# 0001 — Kein Kleinanzeigen-Scraping

## Status

Akzeptiert.

## Kontext

Kleinanzeigen (ehemals eBay Kleinanzeigen) ist für Gebrauchtfahrräder in
Deutschland die mit Abstand größte Plattform. Ein Bot, der sie nicht
durchsucht, verpasst viele Angebote.

## Entscheidung

Kleinanzeigen wird nicht als Quelle angebunden.

## Begründung

- Die Plattform betreibt aktives Bot-Erkennungs- und Blockingsystem
  (Cloudflare-artige Challenges, Rate-Limits, IP-Sperren), das mit einem
  ehrlichen, sich selbst identifizierenden User-Agent nicht zuverlässig zu
  umgehen ist — und genau das ist in diesem Projekt Pflicht
  (`Http`-Client, `USER_AGENT`).
- Die Nutzungsbedingungen von Kleinanzeigen untersagen automatisiertes
  Auslesen ausdrücklich.
- Ein Umgehen der Bot-Erkennung würde zwangsläufig auf Verschleierung
  hinauslaufen (Browser-UA vortäuschen, Sessions rotieren, Captchas lösen
  lassen) — das widerspricht dem Projektgrundsatz "ehrlicher User-Agent,
  keine Umgehung von Bot-Schutz" und ist auch rechtlich nicht sauber.

## Konsequenzen

- Weniger Gesamtabdeckung als theoretisch möglich.
- eBay Browse API (offizielle, erlaubte API) und Neuware-Sale-Quellen
  gleichen einen Teil davon aus.
- Falls Kleinanzeigen später eine offizielle API anbietet, kann das
  revidiert werden.
