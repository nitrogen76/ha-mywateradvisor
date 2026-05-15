from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.core import callback
import logging


from .const import (
    CONF_ENABLE_DEBUG_SENSOR,
    CONF_MAX_REASONABLE_HOURLY_CONS,
    CONF_SKIP_NEGATIVE_CORRECTIONS,
    DEFAULT_ENABLE_DEBUG_SENSOR,
    DEFAULT_MAX_REASONABLE_HOURLY_CONS,
    DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Home Assistant total-increasing safety knobs.
# Set max_reasonable_hourly_cons to 0 in config to allow any positive hourly value.
# Set skip_negative_corrections to False to allow negative correction rows through
# the skip check, though they still will not be added to the increasing total.


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [MWAEnergyTotalSensor(coordinator, entry)]

    if entry.options.get(
        CONF_ENABLE_DEBUG_SENSOR,
        entry.data.get(CONF_ENABLE_DEBUG_SENSOR, DEFAULT_ENABLE_DEBUG_SENSOR),
    ):
        entities.append(MWADebugSensor(coordinator, entry))

    async_add_entities(entities, True)

def device_info(entry):
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "MyWaterAdvisor",
        "manufacturer": "MyWaterAdvisor",
    }


class MWADebugSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "MWA Debug Buckets"
        self._attr_unique_id = f"{entry.entry_id}_mwa_debug_buckets"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data or []
        return len(data)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or []
        anomalies = [entry for entry in data if entry.get("anomaly")]
        estimated = [entry for entry in data if entry.get("estimated")]

        attrs = {
            "estimated_count": len(estimated),
            "anomaly_count": len(anomalies),
            "anomaly_reasons": sorted({
                entry.get("anomaly_reason", "anomaly")
                for entry in anomalies
            }),
        }

        if data:
            sorted_data = sorted(data, key=lambda x: x["dateTime"])
            attrs["oldest_timestamp"] = sorted_data[0]["dateTime"]
            attrs["newest_timestamp"] = sorted_data[-1]["dateTime"]

        return attrs


class MWAEnergyTotalSensor(CoordinatorEntity, SensorEntity, RestoreEntity):

    def __init__(self, coordinator, entry):
        _LOGGER.debug("MWA sensor init called")
        _LOGGER.debug("MWA coordinator passed in: %s", coordinator)
        super().__init__(coordinator)
        _LOGGER.debug("MWA coordinator on self: %s", self.coordinator)

        self._attr_name = "mywateradvisor_Water_Usage_Total"
        self._attr_unique_id = f"{entry.entry_id}_mywateradvisor_water_total"
        self._attr_native_unit_of_measurement = "gal"
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_info = device_info(entry)

        self._total = 0.0
        self._last_timestamp = None

        self._max_reasonable_hourly_cons = entry.options.get(
            CONF_MAX_REASONABLE_HOURLY_CONS,
            entry.data.get(
                CONF_MAX_REASONABLE_HOURLY_CONS,
                DEFAULT_MAX_REASONABLE_HOURLY_CONS,
            ),
        )
        self._skip_negative_corrections = entry.options.get(
            CONF_SKIP_NEGATIVE_CORRECTIONS,
            entry.data.get(
                CONF_SKIP_NEGATIVE_CORRECTIONS,
                DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
            ),
        )


    @callback
    def _handle_coordinator_update(self):
        data = self.coordinator.data

        if data:
            self._process_new_data(data)
            self.hass.async_create_task(self._async_backfill_statistics())

        super()._handle_coordinator_update()

    @property
    def native_value(self):
        return round(self._total, 2)

    @property
    def extra_state_attributes(self):
        return {
            "last_timestamp": self._last_timestamp,
            "max_reasonable_hourly_cons": self._max_reasonable_hourly_cons,
            "skip_negative_corrections": self._skip_negative_corrections,
        }


    def _skip_reason(self, entry):
        val = float(entry.get("cons", 0) or 0)
        api_anomaly_reason = entry.get("anomaly_reason")

        if (
            self._skip_negative_corrections
            and (val < 0 or api_anomaly_reason == "negative_correction")
        ):
            return "negative_correction"

        if (
            self._max_reasonable_hourly_cons
            and val > self._max_reasonable_hourly_cons
        ):
            return "high_outlier"

        if api_anomaly_reason and api_anomaly_reason != "high_outlier":
            return api_anomaly_reason

        return None


    def _process_new_data(self, data):
        if not data:
            return

        entries = data or []

        # filter real entries only
        entries = [e for e in entries if not e.get("estimated")]

        # sort oldest → newest
        entries = sorted(entries, key=lambda x: x["dateTime"])

        # FIRST RUN: baseline only (NO additions)
        if self._last_timestamp is None:
            if entries:
                self._last_timestamp = entries[-1]["dateTime"]
                _LOGGER.debug(
                    "MWA INIT: baseline set to %s",
                    self._last_timestamp,
                )
            return

        # normal processing
        from datetime import datetime

        for entry in entries:
            ts_str = entry["dateTime"]
            ts = datetime.fromisoformat(ts_str)
            last_ts = datetime.fromisoformat(self._last_timestamp)

            val = float(entry.get("cons", 0) or 0)

            if ts > last_ts:
                skip_reason = self._skip_reason(entry)

                if skip_reason:
                    _LOGGER.warning(
                        "MWA SKIP: ts=%s cons=%s reason=%s total=%s",
                        ts_str,
                        val,
                        skip_reason,
                        self._total,
                    )
                    self._last_timestamp = ts_str
                    continue

                new_total = self._total

                if val > 0:
                    new_total = round(self._total + val, 2)

                    # monotonic safety guard
                    if new_total < self._total:
                        _LOGGER.warning(
                            "MWA IGNORE: decreasing total (%s -> %s)",
                            self._total,
                            new_total,
                        )
                    else:
                        self._total = new_total

                _LOGGER.debug(
                    "MWA ADD: ts=%s added=%s total=%s",
                    ts_str,
                    val,
                    self._total,
                )

                # advance cursor immediately
                self._last_timestamp = ts_str

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state:
            try:
                if last_state.state not in (None, "unknown", "unavailable"):
                    self._total = float(last_state.state)
            except ValueError:
                self._total = 0.0

            restored_ts = last_state.attributes.get("last_timestamp")

            # only restore if we actually have one
            if restored_ts:
                self._last_timestamp = restored_ts

        _LOGGER.debug(
            "MWA RESTORE: total=%s last_timestamp=%s",
            self._total,
            self._last_timestamp,
        )

        self._process_new_data(self.coordinator.data)
        self.async_write_ha_state()


    def _handle_coordinator_update(self):
        self._process_new_data(self.coordinator.data)
        super()._handle_coordinator_update()

