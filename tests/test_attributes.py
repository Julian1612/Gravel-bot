from __future__ import annotations

from gravelbot.enrich.attributes import apply_attributes, extract_attributes
from gravelbot.models import Listing


def test_extract_frame_size_letter():
    attrs = extract_attributes("Canyon Grizl Gr. L, top Zustand")
    assert attrs.frame_size == "L"


def test_extract_frame_size_number():
    attrs = extract_attributes("Rose Backroad RH 56, GRX 600")
    assert attrs.frame_size == "56"


def test_extract_frame_size_cm_suffix():
    attrs = extract_attributes("Gravelbike 58cm Carbon")
    assert attrs.frame_size == "58"


def test_extract_year():
    attrs = extract_attributes("Canyon Grizl Modell 2023, wie neu")
    assert attrs.year == 2023


def test_extract_material_carbon():
    assert extract_attributes("Canyon Grizl Carbon Rahmen").material == "Carbon"


def test_extract_material_aluminium():
    assert extract_attributes("Cube Nuroad Alu Gravelbike").material == "Aluminium"


def test_extract_groupset_grx():
    assert extract_attributes("Canyon Grizl mit GRX 810 Di2").groupset == "GRX"


def test_extract_drivetrain_1x():
    attrs = extract_attributes("Gravelbike 1x12 GRX")
    assert attrs.drivetrain == "1x"


def test_extract_drivetrain_2x():
    attrs = extract_attributes("Rennrad 2x11 Ultegra")
    assert attrs.drivetrain == "2x"


def test_extract_attributes_empty_text_returns_none_fields():
    attrs = extract_attributes("")
    assert attrs.frame_size is None
    assert attrs.year is None
    assert attrs.material is None
    assert attrs.groupset is None
    assert attrs.drivetrain is None


def test_apply_attributes_does_not_override_existing_values():
    listing = Listing("s", "1", "Canyon Grizl Gr. L 2023 Carbon GRX 1x12", 1, "u", frame_size="M")
    apply_attributes(listing)
    assert listing.frame_size == "M"
    assert listing.year == 2023
    assert listing.material == "Carbon"
    assert listing.groupset == "GRX"
    assert listing.drivetrain == "1x"
