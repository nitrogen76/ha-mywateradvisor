#!/usr/bin/env python3

import argparse
import json
from api import fetch_data


def main():
    parser = argparse.ArgumentParser(description="MyWaterAdvisor CLI")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--recent", action="store_true")

    args = parser.parse_args()

    data = fetch_data(args.username, args.password)

    if args.recent:
        for entry in data["recent"]:
            status = "EST" if entry["estimated"] else "REAL"
            print(f'{entry["time_local"]}  {entry["cons"]:.2f} gal  {status}')
        return

    if args.pretty:
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps(data))


if __name__ == "__main__":
    main()
