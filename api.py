#!/usr/bin/env python3

# Leo Green <leo@nurgle.net>
# https://github.com/nitrogen76/ha-mywateradvisor

import requests
import datetime
import sys
import argparse
import datetime as dt
import re

## Bastards fixed the time_raw so now i think its local

TIME_RAW_MODE = "utc"   # options: "utc", "local"


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

    if TIME_RAW_MODE == "utc":
        ts_utc = ts.replace(tzinfo=dt.timezone.utc)
        ts_local = ts_utc.astimezone()

    elif TIME_RAW_MODE == "local":
        ts_local = ts.astimezone() if ts.tzinfo else ts.replace(tzinfo=None).astimezone()
        ts_utc = ts_local.astimezone(dt.timezone.utc)

    else:
        raise ValueError(f"Invalid TIME_RAW_MODE: {TIME_RAW_MODE}")

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


 
import datetime as dt


def fetch_data(username, password, hours=48, debug=False, include_estimated=False):
    token = login(username, password)
    meter_id = get_meter_id(token)

    now_utc = dt.datetime.now(dt.timezone.utc)

    # --- STEP 1: determine how many days to fetch ---
    days_needed = (hours // 24) + 2  # buffer so we never miss edge hours

    dates = [
        (now_utc.date() - dt.timedelta(days=i)).isoformat()
        for i in range(days_needed)
    ]

    if debug:
        print(f"[DEBUG] Fetching dates: {dates}")

    # --- STEP 2: fetch + merge ---
    combined = {}

    for d in dates:
        data = get_usage(token, meter_id, d)

        if debug:
            print(f"[DEBUG] {d}: {len(data)} entries")

        local_tz = dt.datetime.now().astimezone().tzinfo

        for entry in data:
    # --- normalize fields ---
            entry["cons"] = entry.get("cons", 0.0)
            entry["estimated"] = entry.get("estimationType", 0) != 0

    # --- handle time ---
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

    # store normalized timestamps
            entry["_ts"] = ts
            entry["_ts_utc"] = ts.astimezone(dt.timezone.utc)
            combined[entry["_ts_utc"].isoformat()] = entry

    # sort everything
    all_entries = sorted(combined.values(), key=lambda x: x["dateTime"])

    if debug:
        print(f"[DEBUG] Total merged entries: {len(all_entries)}")

    # --- STEP 3: filter by time window ---
    cutoff = now_utc - dt.timedelta(hours=hours)

    recent_entries = [
        x for x in all_entries
        if x["_ts_utc"] >= cutoff
    ]

    if not include_estimated:
        	recent_entries = [x for x in recent_entries if not x["estimated"]]

    if debug:
        print(f"[DEBUG] Returning {len(recent_entries)} entries")
        if recent_entries:
            print(f"[DEBUG] Oldest: {recent_entries[0]['dateTime']}")
            print(f"[DEBUG] Newest: {recent_entries[-1]['dateTime']}")
## remove garbage
    for x in recent_entries:
        x.pop("_ts", None)
        x.pop("_ts_utc", None)
    return recent_entries
