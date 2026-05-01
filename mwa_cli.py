#!/usr/bin/env python3

# Leo Green <leo@nurgle.net>
# https://github.com/nitrogen76/ha-mywateradvisor

import argparse
import json
from api import fetch_data


def main():
    parser = argparse.ArgumentParser(description="MyWaterAdvisor CLI")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--formatted", action="store_true")
    parser.add_argument("--include-estimated", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--hours", type=int, default=48)

    args = parser.parse_args()

    data = fetch_data(args.username, 
        args.password,
        hours=args.hours,
        include_estimated=args.include_estimated,
        debug=args.debug
        )

    if args.formatted:
        for entry in data:
            if not args.include_estimated and entry["estimated"]:
                continue

            status = "EST" if entry["estimated"] else "REAL"
            print(f'{entry["time_local"]}  {entry["cons"]:.2f} gal  {status}')
        return

    if args.pretty:
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps(data))


if __name__ == "__main__":
    main()
