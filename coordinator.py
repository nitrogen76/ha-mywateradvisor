"""Fetch delayed hourly readings and update their original statistics hours."""

import datetime as dt
from functools import partial
import hashlib
import logging
from zoneinfo import ZoneInfo

import requests
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyWaterAdvisorApi, MyWaterAdvisorError
from .const import (
    CONF_MAX_REASONABLE_HOURLY_CONS, CONF_SKIP_NEGATIVE_CORRECTIONS,
    CONF_TIME_RAW_MODE, DEFAULT_MAX_REASONABLE_HOURLY_CONS,
    DEFAULT_SKIP_NEGATIVE_CORRECTIONS, DEFAULT_TIME_RAW_MODE,
    DOMAIN, HOURLY_LOOKBACK_DAYS, SCAN_INTERVAL,
)
from .recorder import HourlyStatistics, _hourly_buckets


class MyWaterAdvisorDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         update_interval=SCAN_INTERVAL)
        self.entry = entry
        def option(key, default):
            return entry.options.get(key, entry.data.get(key, default))
        self.time_raw_mode = option(CONF_TIME_RAW_MODE, DEFAULT_TIME_RAW_MODE)
        if self.time_raw_mode not in ("utc", "local"):
            raise ValueError(f"Invalid time mode: {self.time_raw_mode}")
        self.time_zone = (ZoneInfo(hass.config.time_zone)
                          if self.time_raw_mode == "local" else dt.timezone.utc)
        self.max_reasonable = option(CONF_MAX_REASONABLE_HOURLY_CONS,
                                     DEFAULT_MAX_REASONABLE_HOURLY_CONS)
        self.skip_negative = option(CONF_SKIP_NEGATIVE_CORRECTIONS,
                                    DEFAULT_SKIP_NEGATIVE_CORRECTIONS)
        # A timezone change must not mix two interpretations of historical hours.
        zone_key = hashlib.sha256(str(self.time_zone).encode()).hexdigest()[:8]
        # Modern HA entry IDs are uppercase ULIDs; statistics IDs require slugs.
        entry_key = entry.entry_id.lower()
        self.statistic_id = f"{DOMAIN}:{entry_key}_hourly_{self.time_raw_mode}_{zone_key}"
        self.statistics = HourlyStatistics(hass, self.statistic_id)
        self._client = None

    def _fetch(self, start, end):
        if self._client is None:
            self._client = MyWaterAdvisorApi(
                self.entry.data["username"], self.entry.data["password"]
            )
        return self._client.fetch_hourly_data(start, end, self.time_zone)

    async def _async_update_data(self):
        await self.statistics.async_load()
        now = dt.datetime.now(dt.timezone.utc)
        replay_from = (now - dt.timedelta(days=HOURLY_LOOKBACK_DAYS)).replace(
            minute=0, second=0, microsecond=0
        )
        # Include outages longer than the ordinary correction window.
        fetch_from = replay_from
        if self.statistics.last_success is not None:
            fetch_from = min(fetch_from, self.statistics.last_success - dt.timedelta(days=1))
        try:
            raw = await self.hass.async_add_executor_job(partial(self._fetch, fetch_from, now))
        except requests.HTTPError as err:
            if getattr(err.response, "status_code", None) in (401, 403):
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed(f"Unable to retrieve hourly readings: {err}") from err
        except (requests.RequestException, MyWaterAdvisorError) as err:
            raise UpdateFailed(f"Unable to retrieve hourly readings: {err}") from err
        buckets = _hourly_buckets(
            raw, now=now, earliest=fetch_from, time_raw_mode=self.time_raw_mode,
            local_timezone=self.time_zone, max_reasonable=self.max_reasonable,
            skip_negative=self.skip_negative,
        )
        imported = await self.statistics.async_update(buckets, now, replay_from)
        return {"total": self.statistics.total if self.statistics.buckets else None,
                "latest_hour": max(self.statistics.buckets, default=None),
                "fetched_buckets": len(buckets), "imported_hours": imported,
                "statistic_id": self.statistic_id}
