#!/usr/bin/env python3
"""Inspect raw hourly utility readings without changing Home Assistant."""

import argparse
import json

from api import fetch_data


def main():
    parser = argparse.ArgumentParser(description="MyWaterAdvisor hourly readings")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--formatted", action="store_true")
    parser.add_argument("--include-estimated", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--hours", type=int, default=168)
    args = parser.parse_args()
    rows = fetch_data(args.username, args.password, hours=args.hours,
                      include_estimated=args.include_estimated, debug=args.debug)
    if args.formatted:
        for row in rows:
            print(f"{row.get('dateTime')}  {row.get('cons')} gal (hour ending)")
    else:
        print(json.dumps(rows, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
