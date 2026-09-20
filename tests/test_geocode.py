from __future__ import annotations

from gravelbot.enrich.geocode import Geocoder, haversine_km


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeHttp:
    """Simuliert zippopotam.us: bekannte Land/PLZ-Kombination -> Antwort,
    sonst None (wie ein 404 oder ein Netzwerkfehler — Http.get() liefert
    fuer beides None)."""

    def __init__(self, antworten: dict[str, dict | None]):
        self.antworten = antworten  # Schluessel: "<land>/<plz>", z.B. "de/70173"
        self.aufrufe: list[str] = []

    def get(self, url, headers=None):
        self.aufrufe.append(url)
        for schluessel, payload in self.antworten.items():
            if url.endswith(schluessel):
                return None if payload is None else _FakeResponse(payload)
        return None


def test_haversine_zero_distance_for_identical_points():
    assert haversine_km(48.7758, 9.1829, 48.7758, 9.1829) == 0


def test_resolve_returns_none_without_zip():
    geocoder = Geocoder(_FakeHttp({}), {}, 48.7758, 9.1829)
    assert geocoder.resolve(None) is None
    assert geocoder.resolve("") is None


def test_resolve_finds_de_and_caches_result():
    http = _FakeHttp({"de/70173": {"places": [{"latitude": "48.7784", "longitude": "9.1815"}]}})
    cache: dict = {}
    geocoder = Geocoder(http, cache, 48.7758, 9.1829)

    coords = geocoder.resolve("70173")

    assert coords == (48.7784, 9.1815)
    assert cache["de:70173"] == [48.7784, 9.1815]
    assert len(http.aufrufe) == 1

    # zweiter Aufruf kommt aus dem Cache, kein weiterer HTTP-Request
    geocoder.resolve("70173")
    assert len(http.aufrufe) == 1


def test_resolve_falls_back_from_de_to_at():
    http = _FakeHttp(
        {
            "de/1010": {"places": []},  # existiert in DE nicht, aber Zippopotam antwortet trotzdem
            "at/1010": {"places": [{"latitude": "48.2082", "longitude": "16.3738"}]},
        }
    )
    geocoder = Geocoder(http, {}, 48.7758, 9.1829)

    coords = geocoder.resolve("1010")

    assert coords == (48.2082, 16.3738)


def test_resolve_does_not_permanently_cache_a_transient_network_failure():
    # http.get() liefert None (Timeout, 5xx, ...) fuer alle drei Laender
    http = _FakeHttp({})
    cache: dict = {}
    geocoder = Geocoder(http, cache, 48.7758, 9.1829)

    assert geocoder.resolve("70173") is None
    # Regression: fruehen wurde hier faelschlich {"de:70173": None} gecacht,
    # was diese PLZ dauerhaft von der Geo-Aufloesung ausgeschlossen haette.
    assert cache == {}


def test_resolve_caches_a_genuine_negative_response():
    http = _FakeHttp({"de/99999": {"places": []}, "at/99999": {"places": []}, "ch/99999": {"places": []}})
    cache: dict = {}
    geocoder = Geocoder(http, cache, 48.7758, 9.1829)

    geocoder.resolve("99999")

    assert cache.get("de:99999") is None
    assert "de:99999" in cache  # bewusst negativ gecacht (kein Retry noetig)


def test_distance_uses_home_coordinates():
    http = _FakeHttp({"de/70173": {"places": [{"latitude": "48.7784", "longitude": "9.1815"}]}})
    geocoder = Geocoder(http, {}, 48.7758, 9.1829)
    result = geocoder.distance("70173")
    assert result is not None
    assert result < 1  # Stuttgart-Mitte liegt sehr nah am Home-Default
