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


def test_parse_preisrahmen_accepts_bis_as_a_word():
    assert dialogs.parse_preisrahmen("500 bis 3500") == ((500.0, 3500.0), None)


def test_parse_preisrahmen_rejects_stray_letters_from_the_word_bis():
    # Regression: [-–bis] war eine Zeichenklasse, kein literales "bis" —
    # damit haette z.B. "500 sbi 3500" faelschlich gematcht.
    value, error = dialogs.parse_preisrahmen("500 sbi 3500")
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


def test_parse_zeiten_accepts_bare_hour_without_leading_zero():
    # Regression: '8:00' wurde vorher abgelehnt, weil die Stunde exakt zwei
    # Ziffern haben musste — Nutzer tippen selten fuehrende Nullen.
    value, error = dialogs.parse_zeiten("8:00,19:00")
    assert value == ["08:00", "19:00"]
    assert error is None


def test_parse_zeiten_accepts_just_the_hour():
    value, error = dialogs.parse_zeiten("8,19")
    assert value == ["08:00", "19:00"]
    assert error is None


def test_parse_zeiten_accepts_dot_separator():
    value, error = dialogs.parse_zeiten("8.30")
    assert value == ["08:30"]
    assert error is None


def test_parse_zeiten_accepts_compact_military_style():
    value, error = dialogs.parse_zeiten("800,1930")
    assert value == ["08:00", "19:30"]
    assert error is None


def test_parse_zeiten_rejects_out_of_range_hour():
    value, error = dialogs.parse_zeiten("25:00")
    assert value is None
    assert error is not None


def test_parse_radtypen_accepts_comma_separated_names():
    treffer, error = dialogs.parse_radtypen("gravel, rennrad")
    assert treffer == ["gravel", "rennrad"]
    assert error is None


def test_parse_radtypen_accepts_space_separated_and_labels():
    treffer, error = dialogs.parse_radtypen("Gravel Endurance-Rennrad")
    assert treffer == ["gravel", "endurance_rennrad"]


def test_parse_radtypen_deduplicates_while_keeping_order():
    treffer, _ = dialogs.parse_radtypen("gravel, gravel, rennrad")
    assert treffer == ["gravel", "rennrad"]


def test_parse_radtypen_returns_none_for_no_match():
    treffer, error = dialogs.parse_radtypen("keine ahnung was ich will")
    assert treffer is None
    assert error is None


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


def test_parse_rahmengroesse_accepts_koerpergroesse_in_cm():
    value, error = dialogs.parse_rahmengroesse("178")
    assert error is None
    assert "M" in value or "L" in value


def test_parse_rahmengroesse_accepts_explicit_sizes():
    assert dialogs.parse_rahmengroesse("56,58") == (["56", "58"], None)
    assert dialogs.parse_rahmengroesse("m,l") == (["M", "L"], None)


def test_parse_rahmengroesse_mixes_koerpergroesse_and_direct_sizes():
    value, error = dialogs.parse_rahmengroesse("178, 60")
    assert error is None
    assert "60" in value  # direkte Rahmengroesse bleibt erhalten
    assert len(value) > 1  # plus die aus 178cm abgeleitete Spanne


def test_parse_rahmengroesse_egal_clears_filter():
    assert dialogs.parse_rahmengroesse("egal") == ([], None)
    assert dialogs.parse_rahmengroesse("") == ([], None)
    assert dialogs.parse_rahmengroesse("Alle") == ([], None)


def test_parse_rahmengroesse_rejects_garbage():
    value, error = dialogs.parse_rahmengroesse("keine Ahnung!")
    assert value is None
    assert error is not None


def test_koerpergroesse_bands_are_monotonic_and_cover_realistic_range():
    # Kleine, grosse und Grenzfaelle sollen alle eine sinnvolle Spanne liefern.
    for cm in (150, 160, 168, 175, 182, 188, 195, 205):
        groessen = dialogs._koerpergroesse_zu_rahmengroessen(cm)
        assert groessen  # nie leer
