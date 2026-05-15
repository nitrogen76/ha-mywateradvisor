#!/usr/bin/env python3

# Leo Green <leo@nurgle.net>
# https://github.com/nitrogen76/ha-mywateradvisor

import requests
import datetime as dt
import re
import json
import uuid
from pathlib import Path


# in case your implementation isn't broken
TIME_RAW_MODE = "utc"   # options: "utc", "local"
MAX_REASONABLE_HOURLY_CONS = 2000
MAX_REASONABLE_DAILY_CONS = 10000


API_JS_URL = "https://mywateradvisor2.com/static/js/api.js"
## Fallback to the APP id I know works.
KNOWN_APP_ID = "3a869241-d476-40f6-a923-d789d63db11d"
TOKEN_CACHE_FILE = Path.home() / ".mywateradvisor_token_cache.json"
_APP_ID_CACHE = None

# Store the login cache token in a space place for a homeassistant use
# otherwise just in the CWD for my testing off of it.

HA_STORAGE_DIR = Path("/config/.storage")
if HA_STORAGE_DIR.exists():
    TOKEN_CACHE_FILE = HA_STORAGE_DIR / "mywateradvisor_tokens.json"
else:
    TOKEN_CACHE_FILE = Path.cwd() / "mywateradvisor_tokens.json"


## Get the app id.  It SHOULD be static, but i trust NOTHING.
def fetch_app_id(debug=False):
    try:
        js = requests.get(API_JS_URL, timeout=10).text

        # precise match for app: "UUID"
        m = re.search(r'app:\s*"([0-9a-fA-F\-]{36})"', js)
        if m:
            if debug:
                print("DYNAMIC APP_ID:", m.group(1))
            return m.group(1)

        if debug:
            print("APP_ID not found in JS, falling back")

    except Exception as e:
        if debug:
            print("APP_ID fetch failed:", e)

    return None


def get_app_id(debug=False):
    global _APP_ID_CACHE

    if _APP_ID_CACHE:
        return _APP_ID_CACHE

    dynamic = fetch_app_id(debug=debug)

    if dynamic:
        _APP_ID_CACHE = dynamic
    else:
        _APP_ID_CACHE = KNOWN_APP_ID
        if debug:
            print("Using fallback APP_ID:", KNOWN_APP_ID)

    return _APP_ID_CACHE

BASE_URL = "https://customerportal-api.harmonyencoremdm.com"

def convert_timestamp(ts_str):
    ts = dt.datetime.fromisoformat(ts_str)

    if TIME_RAW_MODE == "utc":
        ts_utc = ts.replace(tzinfo=dt.timezone.utc)
        ts_local = ts_utc.astimezone()

    elif TIME_RAW_MODE == "local":
        ts_local = ts.astimezone() if ts.tzinfo else ts.replace(tzinfo=None).astimezone()
        ts_utc = ts_local.astimezone(dt.timezone.utc)

    else:
        raise ValueError(f"Invalid TIME_RAW_MODE: {TIME_RAW_MODE}")

    return ts_utc, ts_local

def load_cached_token(username, debug=False):
    try:
        if not TOKEN_CACHE_FILE.exists():
            return None

        data = json.loads(TOKEN_CACHE_FILE.read_text())

        token = data.get(username)

        if debug and token:
            print(f"[DEBUG] Using cached token for {username}")

        return token

    except Exception as e:
        if debug:
            print(f"[DEBUG] Failed reading token cache: {e}")

    return None


def save_cached_token(username, token, debug=False):
    try:
        data = {}

        if TOKEN_CACHE_FILE.exists():
            data = json.loads(TOKEN_CACHE_FILE.read_text())

        data[username] = token

        TOKEN_CACHE_FILE.write_text(json.dumps(data, indent=2))

        if debug:
            print(f"[DEBUG] Saved token cache for {username}")

    except Exception as e:
        if debug:
            print(f"[DEBUG] Failed saving token cache: {e}")


def clear_cached_token(username, debug=False):
    try:
        if not TOKEN_CACHE_FILE.exists():
            return

        data = json.loads(TOKEN_CACHE_FILE.read_text())

        if username in data:
            del data[username]
            TOKEN_CACHE_FILE.write_text(json.dumps(data, indent=2))

            if debug:
                print(f"[DEBUG] Cleared cached token for {username}")

    except Exception as e:
        if debug:
            print(f"[DEBUG] Failed clearing token cache: {e}")

def perform_login(username, password, debug=False):
    app_id = get_app_id(debug=debug)

    resp = requests.post(
        f"{BASE_URL}/consumer/login",
        headers={
            "Content-Type": "application/json",
            "x-app-id": app_id,
            "Origin": "https://mywateradvisor2.com",
            "Referer": "https://mywateradvisor2.com/",
        },
        json={
            "email": username,
            "pw": password,
            "type": 1,
            "app": app_id,
            "deviceId": str(uuid.uuid4()),
            "osType": 3,
        },
        timeout=10,
    )

    if debug:
        print("LOGIN STATUS:", resp.status_code)
        print("LOGIN BODY:", resp.text)

    resp.raise_for_status()
    token = resp.json()["token"]
    save_cached_token(username, token, debug=debug)

    return token

def login(username, password, debug=False, force_refresh=False):
    if not force_refresh:
        cached = load_cached_token(username, debug=debug)

        if cached:
            return cached

    return perform_login(username, password, debug=debug)

def get_meter_id(token, debug=False):
    resp = requests.get(
        f"{BASE_URL}/consumer/meters",
        headers={
            "Accept": "application/json",
            "x-access-token": token,
        },
        timeout=10,
    )

    if debug:
        print("METERS STATUS:", resp.status_code)
        print("METERS BODY:", resp.text)

    resp.raise_for_status()
    meters = resp.json()
    return meters[0]["meterCount"]

def get_usage(token, meter_id, date, debug=False):
    url = f"{BASE_URL}/consumption/hourly/{meter_id}/{date}/{date}"
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "x-access-token": token,
        },
        timeout=10,
    )

    if debug:
        print("USAGE STATUS:", resp.status_code)
        print("USAGE BODY:", resp.text)

    resp.raise_for_status()
    return resp.json()


def format_consumption_date(value):
    if isinstance(value, dt.datetime):
        value = value.date()

    if isinstance(value, dt.date):
        return value.strftime("%m-%d-%Y")

    if isinstance(value, str):
        for fmt in ("%m-%d-%Y", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(value, fmt).strftime("%m-%d-%Y")
            except ValueError:
                pass

        return value

    raise TypeError(f"Unsupported date value: {value!r}")


def get_daily_usage(token, meter_id, start_date, end_date, debug=False):
    start = format_consumption_date(start_date)
    end = format_consumption_date(end_date)
    url = f"{BASE_URL}/consumption/daily/{meter_id}/{start}/{end}"

    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "x-access-token": token,
        },
        timeout=10,
    )

    if debug:
        print("DAILY USAGE STATUS:", resp.status_code)
        print("DAILY USAGE BODY:", resp.text)

    resp.raise_for_status()
    return resp.json()


def classify_consumption(cons, max_reasonable):
    if cons < 0:
        return "negative_correction"

    if cons > max_reasonable:
        return "high_outlier"

    return None


def normalize_hourly_entry(entry):
    normalized = dict(entry)
    normalized["cons"] = normalized.get("cons", 0.0)
    normalized["estimated"] = normalized.get("estimationType", 0) != 0

    anomaly = classify_consumption(
        float(normalized.get("cons", 0) or 0),
        MAX_REASONABLE_HOURLY_CONS,
    )
    normalized["anomaly"] = anomaly is not None

    if anomaly:
        normalized["anomaly_reason"] = anomaly

    return normalized


def normalize_daily_entry(entry):
    normalized = dict(entry)
    normalized["cons"] = normalized.get("cons", 0.0)
    normalized["estimated"] = normalized.get("estimationType", 0) != 0

    anomaly = classify_consumption(
        float(normalized.get("cons", 0) or 0),
        MAX_REASONABLE_DAILY_CONS,
    )
    normalized["anomaly"] = anomaly is not None

    if anomaly:
        normalized["anomaly_reason"] = anomaly

    raw = normalized.get("consDate")
    if raw:
        ts = dt.datetime.fromisoformat(raw)
        normalized["date"] = ts.date().isoformat()

    return normalized


def is_auth_error(error):
    status = getattr(error.response, "status_code", None)
    return status in (401, 403)


class MyWaterAdvisorApi:
    def __init__(self, username, password, debug=False):
        self.username = username
        self.password = password
        self.debug = debug
        self.token = login(username, password, debug=debug)
        self._meter_id = None

    def refresh_token(self):
        if self.debug:
            print("[DEBUG] Cached token expired, re-authenticating")

        clear_cached_token(self.username, debug=self.debug)
        self.token = login(
            self.username,
            self.password,
            debug=self.debug,
            force_refresh=True,
        )

    def call_with_token_retry(self, func, *args):
        try:
            return func(self.token, *args, debug=self.debug)
        except requests.HTTPError as e:
            if not is_auth_error(e):
                raise

            self.refresh_token()
            return func(self.token, *args, debug=self.debug)

    @property
    def meter_id(self):
        if self._meter_id is None:
            self._meter_id = self.call_with_token_retry(get_meter_id)

        return self._meter_id

    def fetch_hourly_data(self, hours=48, include_estimated=False):
        now_utc = dt.datetime.now(dt.timezone.utc)
        local_tz = dt.datetime.now().astimezone().tzinfo

        # --- STEP 1: determine how many days to fetch ---
        days_needed = (hours // 24) + 2

        dates = [
            (now_utc.date() + dt.timedelta(days=1) - dt.timedelta(days=i)).isoformat()
            for i in range(days_needed)
        ]

        if self.debug:
            print(f"[DEBUG] Fetching dates: {dates}")

        combined = {}

        for d in dates:
            data = self.call_with_token_retry(get_usage, self.meter_id, d)

            if self.debug:
                print(f"[DEBUG] {d}: {len(data)} entries")

            for raw_entry in data:
                entry = normalize_hourly_entry(raw_entry)

                raw = entry["dateTime"]

                ts = dt.datetime.fromisoformat(raw)

                if TIME_RAW_MODE == "utc":
                    ts = ts.replace(tzinfo=dt.timezone.utc)
                elif TIME_RAW_MODE == "local":
                    ts = ts.replace(tzinfo=local_tz)
                else:
                    raise ValueError(f"Invalid TIME_RAW_MODE: {TIME_RAW_MODE}")

                ts_local = ts.astimezone(local_tz)

                entry["time_local"] = ts_local.strftime("%Y-%m-%d %H:%M")

                entry["_ts"] = ts
                entry["_ts_utc"] = ts.astimezone(dt.timezone.utc)

                combined[entry["_ts_utc"].isoformat()] = entry

        all_entries = sorted(combined.values(), key=lambda x: x["_ts_utc"])

        if self.debug:
            print(f"[DEBUG] Total merged entries: {len(all_entries)}")

        cutoff = now_utc - dt.timedelta(hours=hours)

        recent_entries = [
            x for x in all_entries
            if cutoff <= x["_ts_utc"] <= now_utc
        ]

        if not include_estimated:
            recent_entries = [
                x for x in recent_entries
                if not x["estimated"]
            ]

        if self.debug:
            print(f"[DEBUG] Returning {len(recent_entries)} entries")

            if recent_entries:
                print(f"[DEBUG] Oldest: {recent_entries[0]['dateTime']}")
                print(f"[DEBUG] Newest: {recent_entries[-1]['dateTime']}")

        for x in recent_entries:
            x.pop("_ts", None)
            x.pop("_ts_utc", None)

        return recent_entries

    def fetch_daily_data(self, start_date, end_date, include_estimated=False):
        data = self.call_with_token_retry(
            get_daily_usage,
            self.meter_id,
            start_date,
            end_date,
        )

        entries = [normalize_daily_entry(entry) for entry in data]
        entries = sorted(entries, key=lambda x: x.get("consDate", ""))

        if not include_estimated:
            entries = [
                x for x in entries
                if not x["estimated"]
            ]

        return entries


def fetch_data(username, password, hours=48, debug=False, include_estimated=False):
    client = MyWaterAdvisorApi(username, password, debug=debug)
    return client.fetch_hourly_data(
        hours=hours,
        include_estimated=include_estimated,
    )


def fetch_daily_data(
    username,
    password,
    start_date,
    end_date,
    debug=False,
    include_estimated=False,
):
    client = MyWaterAdvisorApi(username, password, debug=debug)
    return client.fetch_daily_data(
        start_date,
        end_date,
        include_estimated=include_estimated,
    )
