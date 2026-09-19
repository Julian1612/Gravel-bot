from __future__ import annotations

from gravelbot.telegram import dialogs


def test_setup_starten_beginnt_bei_radtyp():
    zustand = dialogs.setup_starten()
    assert zustand.flow == "setup"
    assert zustand.schritt == dialogs.RADTYP
    assert zustand.daten == {"radtypen": []}


def test_naechster_schritt_durchlaeuft_alle_schritte():
    schritt = dialogs.SETUP_SCHRITTE[0]
    gesehen = [schritt]
    while True:
        nxt = dialogs.naechster_schritt(schritt)
        if nxt is None:
            break
        gesehen.append(nxt)
        schritt = nxt
    assert gesehen == dialogs.SETUP_SCHRITTE


def test_toggle_radtyp_adds_and_removes():
    ausgewaehlt = dialogs.toggle_radtyp([], "gravel")
    assert ausgewaehlt == ["gravel"]
    ausgewaehlt = dialogs.toggle_radtyp(ausgewaehlt, "gravel")
    assert ausgewaehlt == []


def test_toggle_radtyp_ignoriert_unbekannten_wert():
    ausgewaehlt = dialogs.toggle_radtyp([], "einrad")
    assert ausgewaehlt == []


def test_parse_plz_valid_and_invalid():
    assert dialogs.parse_plz("70173") == ("70173", None)
    value, error = dialogs.parse_plz("abc")
    assert value is None and error is not None


def test_parse_radius_valid_and_invalid():
    assert dialogs.parse_radius("100") == (100, None)
    value, error = dialogs.parse_radius("-5")
    assert value is None and error is not None
    value, error = dialogs.parse_radius("viel")
    assert value is None and error is not None


def test_parse_preisrahmen_valid():
    value, error = dialogs.parse_preisrahmen("500-3500")
    assert value == (500.0, 3500.0)
    assert error is None


def test_parse_preisrahmen_rejects_inverted_range():
    value, error = dialogs.parse_preisrahmen("3500-500")
    assert value is None
    assert error is not None


def test_parse_preisrahmen_rejects_garbage():
    value, error = dialogs.parse_preisrahmen("teuer")
    assert value is None
    assert error is not None


def test_parse_prozent_valid_and_bounds():
    assert dialogs.parse_prozent("15") == (15.0, None)
    assert dialogs.parse_prozent("15%") == (15.0, None)
    value, error = dialogs.parse_prozent("0")
    assert value is None and error is not None
    value, error = dialogs.parse_prozent("120")
    assert value is None and error is not None


def test_parse_zeiten_valid():
    value, error = dialogs.parse_zeiten("08:00,19:30")
    assert value == ["08:00", "19:30"]
    assert error is None


def test_parse_zeiten_rejects_invalid_format():
    value, error = dialogs.parse_zeiten("8 Uhr")
    assert value is None
    assert error is not None


def test_feld_bearbeiten_setzt_edit_flow_und_rueckkehr():
    zustand = dialogs.feld_bearbeiten(dialogs.RADIUS, {"radius": 100})
    assert zustand.flow == "edit"
    assert zustand.schritt == dialogs.RADIUS
    assert zustand.rueckkehr == "profil"
    assert zustand.daten == {"radius": 100}


def test_dialog_zustand_roundtrip_dict():
    zustand = dialogs.setup_starten()
    wieder = dialogs.DialogZustand.from_dict(zustand.to_dict())
    assert wieder == zustand
