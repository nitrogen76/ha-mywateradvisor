# API Documentation

## Base URL

https://customerportal-api.harmonyencoremdm.com

## Authentication

### POST /consumer/login

Returns auth token.

Payload: { "email": "...", "pw": "...", "type": 1, "app":
"`<app_id>`{=html}", "deviceId": "`<uuid>`{=html}", "osType": 3 }

## Endpoints

### GET /consumer/meters

Returns meter list.

### GET /consumption/hourly/{meter_id}/{start}/{end}

Returns hourly consumption data.

## Data Fields

-   dateTime: ISO timestamp (UTC)
-   cons: consumption value
-   estimationType:
    -   0 = real
    -   non-zero = estimated

## Notes

-   API requires x-app-id header
-   App ID may be dynamically extracted from JS
-   Buckets are hour ENDING. e.g. 12:00 are for the hour that ENDS at 12:00
-   Buckets are not exact, because meter reading in a mesh network is done in batches, and would overwhelm the mesh if all done at once.  Therefore a bucket labeled 12:00 might have ended as early as 11:45.  Don't expect the bucket timing to be exact.  
-   The usage reported is only as good as your meter.  Ours is ultrasonic, so it's very exact.  Your milage may vary.
-   This was all reverse engineered.  If you find different behavior, or find new behavior, please let me know!

## Assumptions

-   In my case, the timestamps are in UTC.  The customer portal shows them as if they were local time, so this might be a configuration error on the part of my city.  If you notice different behavior, please let me know, or even better, send a PR.

## Wishlist

-   If someone knows a way to pull a actual meter read off the customer API portal that'd be awesome.  Much of the gunk in this is trying to turn the hourly bucket reads into a meter that home advisor can use.  If I can just get the meter reading and use that, it simplifies this immensely!
