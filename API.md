# API Documentation

## Base URL

https://customerportal-api.harmonyencoremdm.com

## Authentication

### POST /consumer/login

Returns auth token.

Payload: { "email": `"your@e.mail"`, "pw": `"your_secret_password"`, "type": 1, "app": "`long-string-here"`, "deviceId": "`<uuid>`", "osType": 3 }

## Endpoints

### GET /consumer/meters

Returns meter list.

### GET /consumption/hourly/{meter_id}/{start}/{end}

Returns hourly consumption data.

### GET /consumption/daily/{meter_id}/{start}/{end}

Returns daily consumption data.

The hourly client uses `YYYY-MM-DD` dates, matching the previous working
hourly implementation. The daily endpoint uses `MM-DD-YYYY`.

## Data Fields

-   dateTime: ISO timestamp (UTC)
-   cons: consumption value
-   estimationType:
    -   0 = real
    -   non-zero = estimated
-   estimated: optional boolean accepted by the importer

The importer validates raw rows, replaces repeated timestamps, excludes estimates
and incomplete future hours, and applies the configured outlier/correction guards.

## Notes

-   API requires x-app-id header
-   App ID may be dynamically extracted from JS
-   Buckets are hour ENDING. e.g. 12:00 are for the hour that ENDS at 12:00
-   Buckets are not exact, because meter reading in a mesh network is done in batches, and would overwhelm the mesh if all done at once.  Therefore a bucket labeled 12:00 might have ended as early as 11:45.  Don't expect the bucket timing to be exact.  
-   The usage reported is only as good as your meter.  Ours is ultrasonic, so it's very exact.  Your milage may vary.
-   The portal can publish large positive usage spikes and later back them out with negative correction rows.  By default, negative hourly values and hourly values over 2000 gallons are recorded as zero. Both guards can be configured. Changed readings replace their hourly bucket and rebuild subsequent cumulative statistics; see README.md.
-   This was all reverse engineered.  If you find different behavior, or find new behavior, please let me know!

## Assumptions

-   In my case, the timestamps are in UTC.  The customer portal shows them as if they were local time, so this might be a configuration error on the part of my city.  If you notice different behavior, please let me know, or even better, send a PR.

## Wishlist

-   If someone knows a way to pull a actual meter read off the customer API portal that'd be awesome.  Much of the gunk in this is trying to turn the hourly bucket reads into a meter that home advisor can use.  If I can just get the meter reading and use that, it simplifies this immensely!

## Hourly statistics

Hour-ending API timestamps are converted to UTC and moved back one hour for
Home Assistant statistics starts. The UTC/Local option controls timestamps that
have no explicit offset. External hourly statistics feed the Energy dashboard;
the ordinary sensor only displays the retained ledger total.
