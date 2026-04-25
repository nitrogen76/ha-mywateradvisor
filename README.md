# MyWaterAdvisor Home Assistant Integration

## Overview

This project integrates MyWaterAdvisor data into Home Assistant,
providing water usage metrics and historical tracking.

## Components

-   API client (`api.py`)
-   Home Assistant sensor (`sensor.py`)
-   CLI tool (`mwa_cli.py`)

## Features

-   Fetch hourly water usage
-   Deduplicate and normalize API data
-   Track rolling totals safely
-   Handle estimated vs real readings

## Installation

1.  Copy integration files into Home Assistant
    `custom_components/mywateradvisor`
2.  Configure via UI or config entry
3.  Restart Home Assistant

## Sensors

-   Total Water Usage (gallons)
-   Debug bucket sensor

## Notes

-   Handles API quirks like duplicate timestamps
-   Ignores estimated readings for totals

## Bugs

- Probably.  The API part was easy enough to write, but I needed vibecoding help, as i'm very new to homeassistant for the integrations.

See API.md for more information on assumptions made in my install case.

If they break for your case, let me know.
