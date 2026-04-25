#!/usr/bin/env python3

# Leo Green <leo@nurgle.net>
# https://github.com/nitrogen76/ha-mywateradvisor

import requests
import datetime
import sys
import argparse
import datetime as dt
import re


API_JS_URL = "https://mywateradvisor2.com/static/js/api.js"
## Fallback to the APP id I know works.
KNOWN_APP_ID = "3a869241-d476-40f6-a923-d789d63db11d"

_APP_ID_CACHE = None

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

import uuid

def convert_timestamp(ts_str):
    ts = dt.datetime.fromisoformat(ts_str)

    # assume backend is UTC (based on your testing)
    ts_utc = ts.replace(tzinfo=dt.timezone.utc)
    ts_local = ts_utc.astimezone()

    return ts_utc, ts_local


def login(username, password, debug=False):
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
    return resp.json()["token"]

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

def fetch_data(username, password, hours=24):
    token = login(username, password)
    meter_id = get_meter_id(token)

    now_utc = dt.datetime.now(dt.timezone.utc)

    today_utc = now_utc.date()
    yesterday_utc = today_utc - dt.timedelta(days=1)

    data_yesterday = get_usage(token, meter_id, yesterday_utc.isoformat())
    data_today = get_usage(token, meter_id, today_utc.isoformat())

# merge safely (no overwriting loss)
    combined = {}

    for entry in data_yesterday:
        combined[entry["dateTime"]] = entry

    for entry in data_today:
        combined[entry["dateTime"]] = entry

    data = sorted(
        combined.values(),
        key=lambda x: dt.datetime.fromisoformat(x["dateTime"])
    )

    working = data

    deduped = {}
    for entry in working:
        deduped[entry["dateTime"]] = entry

    sorted_entries = sorted(
        deduped.values(),
        key=lambda x: dt.datetime.fromisoformat(x["dateTime"])
    )

    all_entries = sorted_entries

    real_entries = [
        x for x in all_entries
        if x["estimationType"] == 0
    ]

    latest_real = next(
        (x for x in reversed(all_entries) if x["estimationType"] == 0),
        None
    )

    if latest_real:
        idx = all_entries.index(latest_real)
        recent_entries = all_entries[max(0, idx - hours + 1): idx + 1]
    else:
        recent_entries = []

    recent_entries = sorted(
        recent_entries,
        key=lambda x: dt.datetime.fromisoformat(x["dateTime"])
    )

    recent = []
    for x in recent_entries:
        ts_utc, ts_local = convert_timestamp(x["dateTime"])

        recent.append({
            "time_raw": x["dateTime"],
            "time_local": ts_local.isoformat(),
            "cons": x["cons"],
            "estimated": x["estimationType"] != 0
        })

    total = sum(x["cons"] for x in real_entries)
    max_hour = max((x["cons"] for x in real_entries), default=0)

    latest_entry = real_entries[-1] if real_entries else None

    latest = latest_entry["cons"] if latest_entry else 0

    if latest_entry:
        _, latest_local = convert_timestamp(latest_entry["dateTime"])
        latest_time = latest_local.isoformat()
        latest_raw = latest_entry["dateTime"]
    else:
        latest_time = None
        latest_raw = None

    return {
        "total_gallons": round(total, 2),
        "current_hour": round(latest, 2),
        "max_hour": round(max_hour, 2),
        "entries": len(all_entries),
        "last_timestamp_raw": latest_raw,
        "last_timestamp_local": latest_time,
        "recent": recent
    }
