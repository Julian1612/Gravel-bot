"""Nachrichten-Rendering — reine Funktionen, die Text/Tastatur bauen.

Was gemeldet wird, entscheidet scoring/; wie es aussieht, entscheidet
dieses Modul. Kein I/O, kein Zugriff auf Store oder Telegram-Client.
"""

from __future__ import annotations

import html

from gravelbot.config import RADTYP_LABELS, RADTYPEN
from gravelbot.models import Deal, Profil

Keyboard = list[list[dict[str, str]]]

ICONS = {"price_drop": "📉", "under_market": "🔥"}

RADIUS_PRESETS = [25, 50, 100, 200, 400]
SCHWELLE_PRESETS = [10, 15, 20, 25]


def _btn(text: str, callback_data: str) -> dict[str, str]:
    return {"text": text, "callback_data": callback_data}


def fmt_eur(value: float) -> str:
    return f"{value:,.0f} €".replace(",", ".")


def render_help() -> str:
    return (
        "<b>Gravel Deal Bot</b>\n\n"
        "/setup — Suchprofil neu einrichten\n"
        "/profil — aktuelles Profil ansehen und bearbeiten\n"
        "/zeiten — Digest-Uhrzeiten setzen\n"
        "/schwelle — Deal-Schwellenwerte setzen\n"
        "/markt — Marktpreise & Neupreise je Modell\n"
        "/merkliste — gemerkte Inserate\n"
        "/suche <Text> — Freitextsuche ueber alle Quellen\n"
        "/scan — Lauf sofort anstossen\n"
        "/pause — Suche pausieren/fortsetzen\n"
        "/reset — Profil auf Standardwerte zuruecksetzen"
    )


def render_deal(deal: Deal) -> str:
    lg = deal.listing
    lines = [
        f"{ICONS.get(deal.reason, '🚲')} <b>{html.escape(deal.headline)}</b>",
        f"<b>{html.escape(lg.title)}</b>",
    ]
    price_line = f"💶 <b>{fmt_eur(lg.price_eur)}</b>"
    if deal.previous_price:
        price_line += f"  <s>{fmt_eur(deal.previous_price)}</s>"
    elif deal.reference_price:
        price_line += f"  (Median {fmt_eur(deal.reference_price)})"
    elif lg.list_price_eur:
        price_line += f"  <s>{fmt_eur(lg.list_price_eur)}</s> (UVP)"
    lines.append(price_line)

    meta = []
    if lg.distance_km is not None:
        meta.append(f"📍 {html.escape(lg.location or '?')} · {lg.distance_km:.0f} km")
    elif lg.shipping:
        meta.append("📦 Versand möglich")
    if lg.condition:
        meta.append(html.escape(str(lg.condition)))
    if lg.seller_type == "shop":
        meta.append("🏪 Händler")
    if meta:
        lines.append(" · ".join(meta))

    lines.append(f'\n<a href="{html.escape(lg.url, quote=True)}">Zum Inserat →</a>')
    lines.append(f"<i>{lg.source}</i>")
    return "\n".join(lines)


def render_deal_freitext(listing) -> str:
    lines = [f"🔎 <b>{html.escape(listing.title)}</b>", f"💶 <b>{fmt_eur(listing.price_eur)}</b>"]
    if listing.list_price_eur:
        rabatt = listing.discount_vs_list_pct
        zusatz = f" (−{rabatt:.0f}% ggue. UVP)" if rabatt else ""
        lines[-1] += f"  <s>{fmt_eur(listing.list_price_eur)}</s>{zusatz}"
    meta = []
    if listing.distance_km is not None:
        meta.append(f"📍 {html.escape(listing.location or '?')} · {listing.distance_km:.0f} km")
    elif listing.shipping:
        meta.append("📦 Versand möglich")
    if listing.frame_size:
        meta.append(f"Gr. {listing.frame_size}")
    if meta:
        lines.append(" · ".join(meta))
    lines.append(f'\n<a href="{html.escape(listing.url, quote=True)}">Zum Inserat →</a>')
    lines.append(f"<i>{listing.source}</i>")
    return "\n".join(lines)


def render_setup_step(schritt: str, daten: dict) -> tuple[str, Keyboard | None]:
    from gravelbot.telegram import dialogs

    if schritt == dialogs.RADTYP:
        ausgewaehlt = daten.get("radtypen", [])
        rows = []
        for r in RADTYPEN:
            mark = "✅ " if r in ausgewaehlt else ""
            rows.append([_btn(f"{mark}{RADTYP_LABELS[r]}", f"radtyp:{r}")])
        rows.append([_btn("Weiter →", "radtyp:weiter")])
        return ("Welche Radtypen sollen gesucht werden? (Mehrfachauswahl möglich)", rows)

    if schritt == dialogs.STANDORT:
        return ("An welcher Postleitzahl orientieren wir uns? (4-5 Ziffern, als Text schicken)", None)

    if schritt == dialogs.RADIUS:
        rows = [[_btn(f"{km} km", f"radius:{km}") for km in RADIUS_PRESETS]]
        return ("Wie weit darfst du fahren? Zahl waehlen oder eigenen Wert in km schicken.", rows)

    if schritt == dialogs.PREISRAHMEN:
        return ("In welchem Preisrahmen? Als 'MIN-MAX' schicken, z.B. 500-3500.", None)

    if schritt == dialogs.SCHWELLE:
        rows = [[_btn(f"{p}%", f"schwelle:{p}") for p in SCHWELLE_PRESETS]]
        return ("Ab wie viel Prozent unter Marktwert soll es ein Deal sein?", rows)

    if schritt == dialogs.ZEITEN:
        return ("Zu welchen Uhrzeiten soll der Sammel-Digest kommen? z.B. 08:00,19:00", None)

    return ("Unbekannter Schritt.", None)


def render_profil(
    profil: Profil,
    passende_treffer: int,
    neue_treffer_7d: int,
    quellen_status: list[tuple[str, bool, str | None]],
) -> tuple[str, Keyboard]:
    radtypen_text = ", ".join(RADTYP_LABELS.get(r, r) for r in profil.radtypen)
    lines = [
        "<b>Dein Suchprofil</b>",
        f"🚲 Radtyp: {radtypen_text}",
        f"📍 Standort: PLZ {profil.home_plz or '(nicht gesetzt)'} · Radius {profil.max_distance_km} km",
        f"💶 Preisrahmen: {fmt_eur(profil.min_price_eur)} – {fmt_eur(profil.max_price_eur)}",
        f"🔥 Schwelle: {profil.min_discount_pct:.0f}% unter Markt, "
        f"{profil.min_price_drop_pct:.0f}% Preissenkung",
        f"🕐 Digest-Zeiten: {', '.join(profil.digest_times)}",
        f"⏸️ Pausiert: {'ja' if profil.paused else 'nein'}",
        "",
        f"📊 Treffer im Bestand: {passende_treffer} (davon {neue_treffer_7d} neu in 7 Tagen)",
    ]
    if passende_treffer == 0:
        lines.append("⚠️ Dieses Profil liefert aktuell keine Treffer — Filter pruefen!")

    lines.append("")
    lines.append("<b>Quellen</b>")
    for name, aktiv, grund in quellen_status:
        icon = "✅" if aktiv else "⏭️"
        zusatz = f" — {grund}" if grund else ""
        lines.append(f"{icon} {name}{zusatz}")

    keyboard: Keyboard = [
        [_btn("Radtyp ändern", "edit:radtyp"), _btn("Standort ändern", "edit:standort")],
        [_btn("Radius ändern", "edit:radius"), _btn("Preisrahmen ändern", "edit:preisrahmen")],
        [_btn("Schwelle ändern", "edit:schwelle"), _btn("Zeiten ändern", "edit:zeiten")],
        [_btn("Blockliste ansehen", "blockliste:zeigen")],
        [_btn("Profil zuruecksetzen", "reset:fragen")],
    ]
    return "\n".join(lines), keyboard


def render_markt(zeilen: list[tuple[str, float | None, float | None, int]]) -> str:
    if not zeilen:
        return "Noch keine Marktdaten gesammelt — nach ein paar Laeufen mehr hier."
    lines = ["<b>Marktpreise je Modell</b>", ""]
    for model_key, markt_median, neupreis_median, anzahl in sorted(zeilen):
        zeile = f"• <b>{html.escape(model_key)}</b>"
        if markt_median:
            zeile += f" — Gebraucht-Median {fmt_eur(markt_median)}"
        if neupreis_median:
            zeile += f" · Neupreis-Referenz {fmt_eur(neupreis_median)}"
        zeile += f" ({anzahl} Datenpunkte)"
        lines.append(zeile)
    return "\n".join(lines)


def render_merkliste(items: dict[str, dict]) -> tuple[str, Keyboard]:
    if not items:
        return "Deine Merkliste ist leer.", []
    lines = ["<b>Merkliste</b>"]
    rows: Keyboard = []
    for key, entry in items.items():
        lines.append(f'• <a href="{html.escape(entry["url"], quote=True)}">{html.escape(entry["title"])}</a>')
        rows.append([_btn(f"❌ entfernen: {entry['title'][:24]}", f"merkliste:entfernen:{key}")])
    return "\n".join(lines), rows


def render_blockliste(blockliste: dict) -> tuple[str, Keyboard]:
    verkaeufer = blockliste.get("verkaeufer", [])
    inserate = blockliste.get("inserate", {})
    lines = ["<b>Blockliste</b>", ""]
    rows: Keyboard = []
    lines.append("<b>Verkaeufer</b>")
    if not verkaeufer:
        lines.append("(keine)")
    for name in verkaeufer:
        lines.append(f"• {html.escape(name)}")
        rows.append([_btn(f"↩️ entsperren: {name[:24]}", f"blockliste:verkaeufer_entsperren:{name}")])
    lines.append("")
    lines.append("<b>Inserate</b>")
    if not inserate:
        lines.append("(keine)")
    for key, entry in inserate.items():
        lines.append(f"• {html.escape(entry['title'])}")
        rows.append([_btn(f"↩️ entsperren: {entry['title'][:24]}", f"blockliste:inserat_entsperren:{key}")])
    return "\n".join(lines), rows


def render_reset_bestaetigung() -> tuple[str, Keyboard]:
    rows = [[_btn("Ja, zuruecksetzen", "reset:ja"), _btn("Abbrechen", "reset:nein")]]
    return "Profil wirklich auf Standardwerte zuruecksetzen?", rows
