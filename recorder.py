"""Import hour-ending utility readings as external hourly statistics.

The saved ledger is authoritative for this series. Rebuild running sums from it
so re-fetches, late readings and changed readings never increment a total twice.
"""

import datetime as dt
from decimal import Decimal, InvalidOperation
import logging

from .const import DOMAIN, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)
_HOUR = dt.timedelta(hours=1)


def _bucket_start(entry, time_raw_mode="utc", local_timezone=None):
    """Translate the utility's hour END to HA's UTC hour START."""
    if time_raw_mode not in ("utc", "local"):
        raise ValueError(f"Invalid time mode: {time_raw_mode}")
    timestamp = dt.datetime.fromisoformat(entry["dateTime"])
    if timestamp.tzinfo is None:
        timezone = dt.timezone.utc if time_raw_mode == "utc" else local_timezone
        if timezone is None:
            raise ValueError("Local timestamps require a configured timezone")
        timestamp = timestamp.replace(tzinfo=timezone)
        if time_raw_mode == "local" and (
            timestamp.replace(fold=0).utcoffset() != timestamp.replace(fold=1).utcoffset()
        ):
            raise ValueError("Ambiguous or nonexistent local hour requires an explicit offset")
    timestamp = timestamp.astimezone(dt.timezone.utc)
    if timestamp.minute or timestamp.second or timestamp.microsecond:
        raise ValueError("Bucket timestamp is not aligned to a UTC hour")
    return timestamp - _HOUR


def _hourly_buckets(
    data, *, now, earliest, time_raw_mode="utc", local_timezone=None,
    max_reasonable=2000.0, skip_negative=True,
):
    """Return validated, completed, real buckets keyed by UTC start.

    Repeated timestamps describe the same bucket; the last real row wins.
    Missing/invalid/estimated rows do not erase a previously stored real bucket.
    Rejected numeric outliers explicitly replace a previously accepted value
    with zero, which also corrects the running sums downstream.
    """
    buckets = {}
    for entry in data:
        if entry.get("estimated", False) or entry.get("estimationType", 0) not in (
            0, "0", None,
        ):
            continue
        try:
            start = _bucket_start(entry, time_raw_mode, local_timezone)
            consumption = Decimal(str(entry["cons"]))
            if not consumption.is_finite():
                raise ValueError("Consumption is not finite")
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            _LOGGER.warning("Skipping invalid hourly reading %s: %s", entry, exc)
            continue
        if start < earliest or start + _HOUR > now:
            continue
        if (skip_negative and consumption < 0) or (
            max_reasonable > 0 and consumption > Decimal(str(max_reasonable))
        ):
            _LOGGER.warning("Recording rejected hourly value %s at %s as zero", consumption, start)
            consumption = Decimal(0)
        buckets[start.isoformat()] = float(consumption.quantize(Decimal("0.01")))
    return buckets


def _statistics_from_ledger(buckets, import_from=None):
    """Build cumulative rows, including a zero baseline before the first hour.

    Empty hours between known buckets carry the total forward. They may be
    replaced by delayed real readings on a subsequent poll.
    """
    if not buckets:
        return []
    first = dt.datetime.fromisoformat(min(buckets))
    last = dt.datetime.fromisoformat(max(buckets))
    start = first - _HOUR
    total = Decimal(0)
    statistics = []
    while start <= last:
        total += Decimal(str(buckets.get(start.isoformat(), 0)))
        if import_from is None or start >= import_from:
            statistics.append({"start": start, "state": float(total), "sum": float(total)})
        start += _HOUR
    return statistics


class HourlyStatistics:
    """Persist buckets and publish a separate, integration-owned series."""

    def __init__(self, hass, statistic_id):
        from homeassistant.helpers.storage import Store

        self.hass = hass
        self.statistic_id = statistic_id
        self._store = Store(hass, STORAGE_VERSION, statistic_id.replace(":", "."))
        self.buckets = {}
        self.last_success = None
        self._loaded = False

    async def async_load(self):
        if self._loaded:
            return
        saved = await self._store.async_load() or {}
        self.buckets = saved.get("buckets", {})
        raw = saved.get("last_success")
        self.last_success = dt.datetime.fromisoformat(raw) if raw else None
        self._loaded = True

    async def async_update(self, buckets, now, replay_from):
        from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
        from homeassistant.components.recorder.statistics import async_add_external_statistics
        from homeassistant.util.unit_conversion import VolumeConverter

        merged = {**self.buckets, **buckets}
        if not merged:
            return 0
        # Replay the overlap even if unchanged: an interrupted recorder queue is
        # recovered on restart. Corrections propagate through every later hour.
        changed = [dt.datetime.fromisoformat(key) for key, value in buckets.items()
                   if key not in self.buckets or self.buckets[key] != value]
        import_from = min([replay_from, *changed])
        if not self.buckets:
            import_from = None  # Include the initial zero baseline.
        first = dt.datetime.fromisoformat(min(merged))
        if import_from is not None and import_from <= first:
            import_from = first - _HOUR
        rows = _statistics_from_ledger(merged, import_from)
        metadata = {
            "has_sum": True,
            "name": "MyWaterAdvisor Hourly Water Consumption",
            "source": DOMAIN,
            "statistic_id": self.statistic_id,
            "unit_class": VolumeConverter.UNIT_CLASS,
            "unit_of_measurement": "gal",
        }
        try:
            from homeassistant.components.recorder.models import StatisticMeanType
        except ImportError:
            metadata["has_mean"] = False
        else:
            metadata["mean_type"] = StatisticMeanType.NONE
        async_add_external_statistics(
            self.hass, StatisticMetaData(**metadata),
            [StatisticData(**row) for row in rows],
        )
        await self._store.async_save({"buckets": merged, "last_success": now.isoformat()})
        self.buckets = merged
        self.last_success = now
        return len(rows)

    @property
    def total(self):
        return float(sum((Decimal(str(value)) for value in self.buckets.values()), Decimal(0)))
