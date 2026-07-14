#!/usr/bin/env python3

"""Minimal MyWaterAdvisor API client for Home Assistant.

The API's current monthly consumption value is treated as a cumulative meter.
Home Assistant can calculate usage from the difference between successive values,
so there is no need to retrieve or reconstruct hourly buckets.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://customerportal-api.harmonyencoremdm.com"
PORTAL_URL = "https://mywateradvisor2.com"
API_JS_URL = f"{PORTAL_URL}/static/js/api.js"

# Known working fallback if the portal JavaScript cannot be retrieved or parsed.
KNOWN_APP_ID = "3a869241-d476-40f6-a923-d789d63db11d"

REQUEST_TIMEOUT = 15
_APP_ID_CACHE: str | None = None

HA_STORAGE_DIR = Path("/config/.storage")
TOKEN_CACHE_FILE = (
    HA_STORAGE_DIR / "mywateradvisor_tokens.json"
    if HA_STORAGE_DIR.exists()
    else Path.cwd() / "mywateradvisor_tokens.json"
)


class MyWaterAdvisorError(RuntimeError):
    """Base error for this API client."""


class InvalidConsumptionData(MyWaterAdvisorError):
    """Raised when the API returns an unexpected consumption payload."""


def _portal_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": PORTAL_URL,
        "Referer": f"{PORTAL_URL}/",
    }


def fetch_app_id(session: requests.Session, debug: bool = False) -> str | None:
    """Try to discover the current application ID from the portal JavaScript."""
    try:
        response = session.get(API_JS_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        match = re.search(r'app:\s*"([0-9a-fA-F-]{36})"', response.text)
        if match:
            app_id = match.group(1)
            if debug:
                _LOGGER.debug("Discovered app ID %s", app_id)
            return app_id

        _LOGGER.warning("App ID not found in portal JavaScript; using fallback")
    except requests.RequestException as exc:
        _LOGGER.warning("Unable to retrieve app ID; using fallback: %s", exc)

    return None


def get_app_id(session: requests.Session, debug: bool = False) -> str:
    global _APP_ID_CACHE

    if _APP_ID_CACHE is None:
        _APP_ID_CACHE = fetch_app_id(session, debug=debug) or KNOWN_APP_ID

    return _APP_ID_CACHE


def _read_token_cache() -> dict[str, str]:
    if not TOKEN_CACHE_FILE.exists():
        return {}

    try:
        data = json.loads(TOKEN_CACHE_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _LOGGER.warning("Unable to read token cache %s: %s", TOKEN_CACHE_FILE, exc)
        return {}

    return data if isinstance(data, dict) else {}


def load_cached_token(username: str) -> str | None:
    token = _read_token_cache().get(username)
    return token if isinstance(token, str) and token else None


def save_cached_token(username: str, token: str) -> None:
    data = _read_token_cache()
    data[username] = token

    try:
        TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_FILE.write_text(json.dumps(data, indent=2))
        TOKEN_CACHE_FILE.chmod(0o600)
    except OSError as exc:
        _LOGGER.warning("Unable to save token cache %s: %s", TOKEN_CACHE_FILE, exc)


def clear_cached_token(username: str) -> None:
    data = _read_token_cache()
    if username not in data:
        return

    del data[username]
    try:
        TOKEN_CACHE_FILE.write_text(json.dumps(data, indent=2))
        TOKEN_CACHE_FILE.chmod(0o600)
    except OSError as exc:
        _LOGGER.warning("Unable to update token cache %s: %s", TOKEN_CACHE_FILE, exc)


def _is_auth_error(exc: requests.HTTPError) -> bool:
    return exc.response is not None and exc.response.status_code in (401, 403)


class MyWaterAdvisorApi:
    """Small client exposing only the cumulative current-month consumption."""

    def __init__(self, username: str, password: str, debug: bool = False) -> None:
        self.username = username
        self.password = password
        self.debug = debug
        self.session = requests.Session()
        self.token = load_cached_token(username) or self._perform_login()
        self._meter_id: int | None = None

    def _perform_login(self) -> str:
        app_id = get_app_id(self.session, debug=self.debug)

        response = self.session.post(
            f"{BASE_URL}/consumer/login",
            headers={**_portal_headers(), "x-app-id": app_id},
            json={
                "email": self.username,
                "pw": self.password,
                "type": 1,
                "app": app_id,
                "deviceId": str(uuid.uuid4()),
                "osType": 3,
            },
            timeout=REQUEST_TIMEOUT,
        )

        if self.debug:
            _LOGGER.debug("Login status: %s", response.status_code)

        response.raise_for_status()

        try:
            token = response.json()["token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise MyWaterAdvisorError("Login response did not contain a token") from exc

        if not isinstance(token, str) or not token:
            raise MyWaterAdvisorError("Login returned an invalid token")

        save_cached_token(self.username, token)
        return token

    def refresh_token(self) -> None:
        _LOGGER.info("MyWaterAdvisor token was rejected; logging in again")
        clear_cached_token(self.username)
        self.token = self._perform_login()

    def _request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        """Make an authenticated request, retrying once after an auth failure."""
        for attempt in range(2):
            headers = dict(kwargs.pop("headers", {}))
            headers["x-access-token"] = self.token

            response = self.session.request(
                method,
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )

            if self.debug:
                _LOGGER.debug("%s %s -> %s", method, url, response.status_code)

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                if attempt == 0 and _is_auth_error(exc):
                    self.refresh_token()
                    continue
                raise

            try:
                return response.json()
            except ValueError as exc:
                raise MyWaterAdvisorError(
                    f"API returned invalid JSON from {url}"
                ) from exc

        raise AssertionError("unreachable")

    @property
    def meter_id(self) -> int:
        if self._meter_id is not None:
            return self._meter_id

        data = self._request_json(
            "GET",
            f"{BASE_URL}/consumer/meters",
            headers={"Accept": "application/json"},
        )

        try:
            meter_id = int(data[0]["meterCount"])
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise MyWaterAdvisorError("No valid meter was returned") from exc

        self._meter_id = meter_id
        return meter_id

    def fetch_monthly_consumption(
        self,
        month: str | None = None,
    ) -> float | None:
        """Return the cumulative consumption for one API month.

        The API appears to roll its dates over on UTC, so the default month is
        derived from the current UTC date. A zero value is deliberately ignored
        because it is indistinguishable from a temporary API/rollover failure.

        Returning ``None`` means the caller should retain its previous reading.
        """
        requested_month = month or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")

        if not re.fullmatch(r"\d{4}-\d{2}", requested_month):
            raise ValueError(f"Invalid month {requested_month!r}; expected YYYY-MM")

        url = (
            f"{BASE_URL}/v1.1/consumption/monthly/"
            f"{self.meter_id}/{requested_month}/{requested_month}"
        )
        payload = self._request_json("GET", url, headers=_portal_headers())

        if not isinstance(payload, dict):
            raise InvalidConsumptionData("Monthly response was not an object")

        records = payload.get("consumptionData")
        if not isinstance(records, list):
            raise InvalidConsumptionData("Monthly response had no consumptionData list")

        matching_records = [
            record
            for record in records
            if isinstance(record, dict)
            and str(record.get("consDate", ""))[:7] == requested_month
        ]

        if len(matching_records) != 1:
            raise InvalidConsumptionData(
                f"Expected one record for {requested_month}, got {len(matching_records)}"
            )

        record = matching_records[0]

        try:
            consumption = float(record["cons"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidConsumptionData("Monthly record had no valid cons value") from exc

        if consumption < 0:
            raise InvalidConsumptionData(
                f"Negative consumption received for {requested_month}: {consumption}"
            )

        if consumption == 0:
            _LOGGER.warning(
                "Zero consumption received for %s and ignored; retaining previous value",
                requested_month,
            )
            return None

        # The API exposes ordinary binary floating-point noise such as
        # 3938.199999999997. Tenths match the meter's apparent precision.
        return round(consumption, 1)


# Convenience function for callers that do not need to retain a client object.
def fetch_monthly_consumption(
    username: str,
    password: str,
    month: str | None = None,
    debug: bool = False,
) -> float | None:
    client = MyWaterAdvisorApi(username, password, debug=debug)
    return client.fetch_monthly_consumption(month=month)


# Compatibility name for a simple integration rewrite. Unlike the former
# implementation, this returns one cumulative float (or None), not hourly rows.
def fetch_data(
    username: str,
    password: str,
    debug: bool = False,
) -> float | None:
    return fetch_monthly_consumption(
        username=username,
        password=password,
        debug=debug,
    )
