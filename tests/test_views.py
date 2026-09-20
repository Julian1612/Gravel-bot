from __future__ import annotations

from gravelbot.config import BOT_COMMANDS
from gravelbot.models import Deal, Listing, Profil
from gravelbot.telegram import views


def _listing(**overrides) -> Listing:
    base = dict(
        source="ebay", source_id="1", title="Canyon Grizl", price_eur=2000, url="https://example.test/1"
    )
    base.update(overrides)
    return Listing(**base)


def test_safe_cb_leaves_short_values_untouched():
    assert views._safe_cb("merkliste:entfernen:", "ebay:123") == "merkliste:entfernen:ebay:123"


def test_safe_cb_truncates_to_telegrams_64_byte_limit():
    long_name = "a" * 100
    cb = views._safe_cb("blockliste:verkaeufer_sperren:", long_name)
    assert len(cb.encode("utf-8")) <= 64


def test_safe_cb_handles_prefix_alone_over_limit():
    cb = views._safe_cb("x" * 70, "irgendwas")
    assert len(cb.encode("utf-8")) <= 64


def test_render_deal_keyboard_has_no_seller_button_without_seller_name():
    kb = views.render_deal_keyboard("bikemarkt:1")
    assert len(kb) == 1
    assert len(kb[0]) == 2


def test_render_deal_keyboard_adds_seller_button_when_present():
    kb = views.render_deal_keyboard("ebay:1", seller_name="radhaus_stuttgart")
    assert len(kb) == 2
    assert "radhaus_stuttgart" in kb[1][0]["callback_data"]


def test_render_deal_keyboard_callback_data_never_exceeds_64_bytes():
    kb = views.render_deal_keyboard("ebay:" + "9" * 80, seller_name="x" * 80)
    for row in kb:
        for button in row:
            assert len(button["callback_data"].encode("utf-8")) <= 64


def test_render_suche_laeuft_escapes_html():
    text = views.render_suche_laeuft("<script>alert(1)</script> & Canyon")
    assert "<script>" not in text
    assert "&amp;" in text


def test_render_deal_escapes_title_and_headline():
    deal = Deal(_listing(title="<b>hack</b>"), "under_market", "<i>50%</i> unter Markt", score=50)
    text = views.render_deal(deal)
    assert "<b>hack</b>" not in text
    assert "&lt;b&gt;hack&lt;/b&gt;" in text


def test_render_deal_shows_previous_price_when_present():
    deal = Deal(_listing(price_eur=900), "price_drop", "Preis gesenkt", score=20, previous_price=1000)
    text = views.render_deal(deal)
    assert "1.000" in text or "1000" in text


def test_render_profil_flags_zero_treffer():
    profil = Profil()
    text, _ = views.render_profil(profil, passende_treffer=0, neue_treffer_7d=0, quellen_status=[])
    assert "keine Treffer" in text


def test_render_profil_has_edit_buttons_for_every_setup_field():
    profil = Profil()
    _, keyboard = views.render_profil(profil, 5, 1, [("bikemarkt", True, None)])
    callback_data = {btn["callback_data"] for row in keyboard for btn in row}
    for feld in ("radtyp", "standort", "radius", "preisrahmen", "schwelle", "zeiten"):
        assert f"edit:{feld}" in callback_data


def test_render_markt_empty():
    assert "Noch keine" in views.render_markt([])


def test_render_markt_shows_both_median_types():
    text = views.render_markt([("canyon grizl", 2000.0, 2500.0, 5)])
    assert "Gebraucht-Median" in text
    assert "Neupreis-Referenz" in text


def test_render_merkliste_empty_has_no_buttons():
    text, kb = views.render_merkliste({})
    assert kb == []
    assert "leer" in text


def test_render_blockliste_shows_both_sections_empty():
    text, kb = views.render_blockliste({})
    assert "(keine)" in text
    assert kb == []


def test_render_help_lists_every_command_except_start():
    text = views.render_help()
    for befehl, _beschreibung in BOT_COMMANDS:
        if befehl == "start":
            assert f"/{befehl}" not in text
        else:
            assert f"/{befehl}" in text


def test_render_help_and_bot_commands_never_drift_apart():
    # Regression-Absicherung fuer die Designentscheidung: render_help() baut
    # sich aus BOT_COMMANDS, es gibt keine zweite, von Hand gepflegte Liste
    # mehr, die veralten koennte.
    befehle_in_hilfe = {wort.lstrip("/") for wort in views.render_help().split() if wort.startswith("/")}
    befehle_in_config = {befehl for befehl, _ in BOT_COMMANDS if befehl != "start"}
    assert befehle_in_hilfe == befehle_in_config


def test_render_start_mentions_setup():
    text = views.render_start()
    assert "/setup" in text
    assert "Willkommen" in text


def test_render_reset_bestaetigung_has_confirm_and_cancel():
    _, kb = views.render_reset_bestaetigung()
    callback_data = {btn["callback_data"] for row in kb for btn in row}
    assert "reset:ja" in callback_data
    assert "reset:nein" in callback_data
