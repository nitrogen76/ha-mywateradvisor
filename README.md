# MyWaterAdvisor API Fetcher

A small Python script to fetch hourly water usage data from the MyWaterAdvisor backend and present it in a sane, usable format.

This project exists because the official UI hides a lot of important details (timestamps, estimation flags, etc.), and the API has some… interesting behavior.

This will eventually become a HomeAdvisor integration
---

## Features

- Authenticates against the MyWaterAdvisor API
- Fetches hourly consumption data
- Merges current + next day to get a full timeline
- Deduplicates overlapping entries
- Preserves **all hourly buckets** (including estimated/future)
- Flags estimated data
- Computes useful stats:
  - Total gallons (real data only)
  - Current hour usage (latest real bucket)
  - Maximum hourly usage
- Outputs both:
  - Raw timestamps (from API)
  - Derived local timestamps

---

## Important Concepts (READ THIS)

### 1. Buckets are hourly, not instantaneous

Each entry represents **an hour of usage**, not a point in time.

Based on real-world testing:


timestamp = END of hour bucket

In my brief testing, buckets end a bit before teh hour closes.  Further testing probably needs to happen.


Example:


2026-04-22T07:00:00 → usage from 06:00–06:59

### Real-world behavior

In practice, bucket boundaries are not exact and may vary by several minutes.

This is consistent with distributed meter networks, where readings are transmitted and aggregated asynchronously rather than at precise time boundaries.

Empirical observations suggest an effective aggregation window on the order of ±10 minutes from the nominal hour.  This could vary as more data is collected.

For this reason, timestamps should be interpreted as approximate bucket labels, not precise event times.


---

### 2. Data may be "in-progress"

The API sometimes returns:

- Completed hours (real data)
- Future hours (estimated placeholders)
- Current hour (partially accumulated)

Use:


estimationType == 0 → REAL data
estimationType != 0 → ESTIMATED / placeholder / no data recieved


---

### 3. Timestamps may be in UTC

Based on testing:

- API timestamps appear to be **UTC**
- Converted to local time in the script

Example:


2026-04-22T12:00:00 (UTC)
→ 2026-04-22T07:00:00-05:00 (local CDT)


---

### 4. Do NOT trust timestamps blindly

This API has inconsistent behavior:

- Buckets may appear "early"
- Current hour may be partially filled
- Future hours may exist with zero usage

**Correct approach:**
- Preserve raw timestamps
- Convert for display only
- Use `estimationType` for truth

---

## Output Format

Example:

```json
{
  "total_gallons": 95.7,
  "current_hour": 33.8,
  "max_hour": 44.1,
  "entries": 25,
  "last_timestamp_raw": "2026-04-22T12:00:00",
  "last_timestamp_local": "2026-04-22T07:00:00-05:00",
  "recent": [
    {
      "time_raw": "2026-04-22T12:00:00",
      "time_local": "2026-04-22T07:00:00-05:00",
      "cons": 33.8,
      "estimated": false
    }
  ]
}
```
## Usage

```bash
./mwa_cli.py USERNAME PASSWORD [--pretty] [--recent]
````

### Arguments

| Argument        | Description |
|----------------|-------------|
| `USERNAME`     | Your MyWaterAdvisor login (email address) |
| `PASSWORD`     | Your MyWaterAdvisor password |
| `pretty`       | Make the JQ readable
| `recent`    | show recent stuff

## How it works

1. Authenticate with the MyWaterAdvisor API and obtain an access token.

2. Fetch hourly usage data for:
   - The requested date
   - The following day  
   (This is required because the API spreads data across day boundaries.)

3. Combine both datasets into a single list.

4. Deduplicate entries using the `dateTime` field as the key  
   (the last occurrence wins if duplicates exist).

5. Sort all entries chronologically by timestamp.

6. Split the data into two logical sets:
   - **all_entries**: every bucket returned by the API (including estimated/future)
   - **real_entries**: only entries where `estimationType == 0`

7. Compute statistics using **real_entries only**:
   - `total_gallons`: sum of all real usage
   - `current_hour`: usage from the latest real bucket
   - `max_hour`: highest hourly usage observed
   - `last_timestamp`: timestamp of the latest real bucket

8. Select recent entries from **all_entries**, anchored to the latest real bucket  
   (prevents returning only future/estimated data).

9. For each output entry:
   - Preserve the original API timestamp (`time_raw`)
   - Generate a derived local timestamp (`time_local`)
   - Include consumption and estimated flag

10. Output the result as JSON.


### Compatibility Notes

This script is based on a specific MyWaterAdvisor deployment (including app ID and API behavior) in Sachse, TX.

Other cities/utilities may use:

- different app IDs
- slightly different API endpoints
- different aggregation or timestamp behavior

If this doesn’t work out of the box for you, you’ll likely need to:

- inspect the API calls (browser dev tools / proxy)
- identify the correct app ID and endpoints
- adjust the script accordingly

If you get it working elsewhere, please share what you found.

If you find documentation on the API, that'd be even better!
