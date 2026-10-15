# MyWaterAdvisor Home Assistant Integration

Import delayed hourly water readings into Home Assistant at the hours when the
water was used. The Energy dashboard uses an integration-owned statistics series;
the ordinary sensor displays the total of the retained hourly readings.

## Installation and upgrade

1. Copy the integration's Python files, `manifest.json`, and `strings.json` into
   `/config/custom_components/mywateradvisor/`.
2. Restart Home Assistant. Configure MyWaterAdvisor under **Settings → Devices &
   services**, or use the existing entry's options.
3. Under the Energy dashboard's water configuration, remove the previous water
   source and select **MyWaterAdvisor Hourly Water Consumption**. The displayed
   total sensor is no longer the statistics source.

Initial setup imports approximately seven days. Each subsequent poll re-fetches
seven days to pick up delayed or corrected readings. After a longer outage, the
fetch range extends back to the last successful update. Corrections older than
the fetch range are not discovered automatically.

The previous statistics are not used or changed. They may be deleted if desired;
this integration does not purge unrelated history or repeatedly delete records on
startup. Actual deletion requires access to the running Home Assistant instance.

## Timestamp handling

Choose **UTC** (the default, including existing installations) or **Local** in
setup or the integration's options. Local uses Home Assistant's configured IANA
timezone, including daylight saving rules. Explicit API timezone offsets are
preserved. A local hour repeated during the autumn clock change cannot be
identified uniquely without an offset; ambiguous or nonexistent local timestamps
are skipped with a warning rather than assigned to an arbitrary hour.

The API documents buckets by the hour **ending**: 12:00 means usage during
11:00–12:00. The importer converts to UTC and subtracts one hour to obtain the
statistics start. Future/incomplete hours and estimated rows are excluded.
Changing the time mode or local timezone creates a separate statistics series;
select the new source in the Energy dashboard after changing that setting.

## Totals and corrections

A saved ledger holds each real hourly bucket by its UTC start timestamp. A
repeated timestamp replaces that bucket rather than adding usage again. Repeated
polls and restarts therefore retain the same total. Changed values and late
readings rebuild cumulative sums for all later retained hours.

Hours missing between known readings provisionally carry the running total
forward. When a real reading arrives, its hour and subsequent sums are replaced.
An explicit zero replaces previous usage; a missing, invalid, or estimated row
does not erase a previously stored real value.

The existing maximum-hourly-usage and negative-correction options apply to this
series. Rejected numeric values are recorded as zero, including when replacing a
previously accepted reading. Set the maximum to 0 to disable the high-value
filter. Disable **Skip negative corrections** to retain signed correction values.
The displayed total may decrease after a correction, so the display sensor has
no `total_increasing` state class and does not produce a competing statistics
series. Its value is consumption since this ledger began, not a physical meter
reading or the current month's total.

## Diagnostics

Enable the debug sensor to see how many buckets were accepted in the latest
fetch, how many statistics hours were queued, the statistics ID, and the latest
retained hour. Both sensors expose the statistics ID for dashboard configuration.

`mwa_cli.py` can inspect raw hourly readings independently. Its timestamps are raw
hour-ending values. The CLI is not used to feed Home Assistant.

## Verification

Run `python3 -m unittest discover -s tests -v` from this repository. The offline
suite covers the API response contract, timestamp conversion, duplicate buckets,
late readings, corrections, replay and persistence across restarts. Home
Assistant services and network calls are mocked; the tests do not confirm a live
database import or the dashboard configuration.
