import datetime as dt
import logging

from .api import TIME_RAW_MODE

_LOGGER = logging.getLogger(__name__)


def _bucket_start(entry):
    raw = entry.get("dateTime")
    if not raw:
        return None

    try:
        timestamp = dt.datetime.fromisoformat(raw)
    except ValueError:
        _LOGGER.warning("MWA STATS: invalid bucket timestamp %s", raw)
        return None

    if timestamp.tzinfo is None:
        if TIME_RAW_MODE == "utc":
            timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
        elif TIME_RAW_MODE == "local":
            timestamp = timestamp.replace(
                tzinfo=dt.datetime.now().astimezone().tzinfo
            )
        else:
            raise ValueError(f"Invalid TIME_RAW_MODE: {TIME_RAW_MODE}")

    return timestamp.astimezone(dt.timezone.utc).replace(
        minute=0,
        second=0,
        microsecond=0,
    )


def _hourly_buckets(data):
    buckets = {}

    for entry in data or []:
        if entry.get("estimated"):
            continue

        start = _bucket_start(entry)
        if start is None:
            continue

        try:
            consumption = float(entry.get("cons", 0) or 0)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "MWA STATS: invalid consumption for %s: %s",
                entry.get("dateTime"),
                entry.get("cons"),
            )
            continue

        buckets[start] = round(buckets.get(start, 0.0) + max(consumption, 0.0), 2)

    return [(start, buckets[start]) for start in sorted(buckets)]


def _last_stat_values(last_stats, statistic_id):
    if not last_stats or statistic_id not in last_stats:
        return None, 0.0

    latest = last_stats[statistic_id][0]
    last_start = latest.get("start")
    last_sum = latest.get("sum")

    return last_start, float(last_sum or 0.0)


def _as_timestamp(value):
    if isinstance(value, dt.datetime):
        return value.timestamp()

    return float(value)


def _baseline_sum(records, buckets, fallback_start, fallback_sum):
    bucket_totals = {}
    running_bucket_total = 0.0

    for start, consumption in buckets:
        running_bucket_total = round(running_bucket_total + consumption, 2)
        bucket_totals[start.timestamp()] = running_bucket_total

    for record in sorted(records, key=lambda item: _as_timestamp(item["start"])):
        start_ts = _as_timestamp(record["start"])
        if start_ts in bucket_totals and record.get("sum") is not None:
            return round(float(record["sum"]) - bucket_totals[start_ts], 2)

    if fallback_start is not None:
        first_start = buckets[0][0].timestamp()
        if _as_timestamp(fallback_start) < first_start:
            return fallback_sum

    return 0.0


def _metadata(StatisticMetaData, StatisticMeanType, statistic_id, name, unit_class):
    kwargs = {
        "has_sum": True,
        "name": name,
        "source": "recorder",
        "statistic_id": statistic_id,
        "unit_class": unit_class,
        "unit_of_measurement": "gal",
    }

    if StatisticMeanType is None:
        kwargs["has_mean"] = False
    else:
        kwargs["mean_type"] = StatisticMeanType.NONE

    return StatisticMetaData(**kwargs)


async def async_import_bucket_statistics(hass, statistic_id, name, data):
    buckets = _hourly_buckets(data)
    if not buckets:
        _LOGGER.debug("MWA STATS: no real buckets to import")
        return 0

    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
    from homeassistant.components.recorder.statistics import (
        async_import_statistics,
        get_last_statistics,
        statistics_during_period,
    )
    from homeassistant.util.unit_conversion import VolumeConverter

    try:
        from homeassistant.components.recorder.models import StatisticMeanType
    except ImportError:
        StatisticMeanType = None

    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics,
        hass,
        1,
        statistic_id,
        True,
        {"sum"},
    )
    last_start, running_sum = _last_stat_values(last_stats, statistic_id)
    period_stats = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        buckets[0][0],
        None,
        {statistic_id},
        "hour",
        None,
        {"sum"},
    )
    existing_records = period_stats.get(statistic_id, []) if period_stats else []
    running_sum = _baseline_sum(existing_records, buckets, last_start, running_sum)

    statistics = []
    for start, consumption in buckets:
        running_sum = round(running_sum + consumption, 2)
        statistics.append(
            StatisticData(
                start=start,
                state=running_sum,
                sum=running_sum,
            )
        )

    if not statistics:
        _LOGGER.debug("MWA STATS: no new buckets for %s", statistic_id)
        return 0

    metadata = _metadata(
        StatisticMetaData,
        StatisticMeanType,
        statistic_id,
        name,
        VolumeConverter.UNIT_CLASS,
    )

    async_import_statistics(hass, metadata, statistics)
    _LOGGER.info(
        "MWA STATS: imported %s bucket(s) for %s",
        len(statistics),
        statistic_id,
    )
    return len(statistics)
