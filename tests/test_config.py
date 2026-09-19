from __future__ import annotations

import pytest

from gravelbot.config import (
    BIKE_COMPONENTS_CATEGORY_PATH,
    BIKEMARKT_CATEGORIES,
    BUYCYCLE_QUERY,
    CANYON_CATEGORY,
    EBAY_QUERY,
    RADTYP_LABELS,
    RADTYPEN,
    ROSE_SALE_CATEGORY,
)

MAPPINGS = [
    BIKEMARKT_CATEGORIES,
    BUYCYCLE_QUERY,
    EBAY_QUERY,
    CANYON_CATEGORY,
    ROSE_SALE_CATEGORY,
    BIKE_COMPONENTS_CATEGORY_PATH,
]


@pytest.mark.parametrize("mapping", MAPPINGS)
def test_every_radtyp_has_a_mapping_entry(mapping):
    for radtyp in RADTYPEN:
        assert radtyp in mapping, f"{radtyp} fehlt in {mapping}"


def test_every_radtyp_has_a_label():
    for radtyp in RADTYPEN:
        assert radtyp in RADTYP_LABELS
