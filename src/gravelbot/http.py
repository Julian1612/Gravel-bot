"""HTTP-Client mit Rate-Limit und Retries.

Alle Quellen benutzen ausschliesslich diese Klasse — keine nackten
requests.get-Aufrufe. So bleiben Hoeflichkeitsregeln (ehrlicher
User-Agent, Wartezeit zwischen Requests) an einer Stelle durchgesetzt.
"""

from __future__ import annotations

import logging
import time

import requests

from gravelbot.config import Settings

log = logging.getLogger("gravel.http")


class Http:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept-Language": "de-DE,de;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            }
        )

    def get(self, url: str, headers: dict[str, str] | None = None) -> requests.Response | None:
        for attempt in range(1, self.settings.max_retries + 1):
            wait = self.settings.request_delay_seconds - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                resp = self.session.get(url, headers=headers, timeout=self.settings.timeout_seconds)
            except requests.RequestException as exc:
                log.warning("GET %s fehlgeschlagen (%s/%s): %s", url, attempt, self.settings.max_retries, exc)
                time.sleep(2**attempt)
                continue
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                time.sleep(int(resp.headers.get("Retry-After", 5 * attempt)))
                continue
            if 400 <= resp.status_code < 500:
                log.warning("GET %s -> HTTP %s", url, resp.status_code)
                return None
            time.sleep(2**attempt)
        log.error("GET %s endgueltig fehlgeschlagen", url)
        return None

    def post(
        self,
        url: str,
        json_body: dict | None = None,
        data: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response | None:
        wait = self.settings.request_delay_seconds - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        try:
            return self.session.post(
                url,
                json=json_body,
                data=data,
                headers=headers,
                timeout=self.settings.timeout_seconds,
            )
        except requests.RequestException as exc:
            log.warning("POST %s fehlgeschlagen: %s", url, exc)
            return None
