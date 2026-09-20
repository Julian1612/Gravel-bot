"""Geocoding: PLZ -> Koordinaten, mit Cache im State."""

from __future__ import annotations

import math

from gravelbot.http import Http


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Geocoder:
    def __init__(self, http: Http, cache: dict, home_lat: float, home_lon: float):
        self.http = http
        self.cache = cache
        self.home_lat = home_lat
        self.home_lon = home_lon

    def resolve(self, zip_code: str | None) -> tuple[float, float] | None:
        """PLZ -> (lat, lon), mit Cache. Probiert DE/AT/CH der Reihe nach."""
        if not zip_code:
            return None
        for country in ("de", "at", "ch"):
            ck = f"{country}:{zip_code}"
            if ck in self.cache:
                hit = self.cache[ck]
                if hit:
                    return float(hit[0]), float(hit[1])
                continue
            resp = self.http.get(f"https://api.zippopotam.us/{country}/{zip_code}")
            if resp is None:
                # Kein Cache-Eintrag: das kann ein 404 (PLZ existiert in
                # diesem Land nicht — Http.get() liefert dafuer auch None)
                # oder ein transienter Netzwerkfehler sein. Im Zweifel lieber
                # naechstes Mal erneut versuchen, statt eine PLZ wegen eines
                # einmaligen Ausfalls dauerhaft ungeocodet zu lassen.
                continue
            try:
                places = resp.json().get("places") or []
                lat, lon = float(places[0]["latitude"]), float(places[0]["longitude"])
            except (ValueError, KeyError, IndexError, TypeError):
                self.cache[ck] = None
                continue
            self.cache[ck] = [lat, lon]
            return lat, lon
        return None

    def distance(self, zip_code: str | None) -> float | None:
        coords = self.resolve(zip_code)
        if coords is None:
            return None
        return round(haversine_km(self.home_lat, self.home_lon, *coords), 1)
