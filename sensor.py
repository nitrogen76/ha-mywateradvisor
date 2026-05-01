from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["mywateradvisor"][entry.entry_id]
    async_add_entities([MWAEnergyTotalSensor(coordinator),
						MWADebugSensor(coordinator),
	], True)

class MWADebugSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "MWA Debug Buckets"
        self._attr_unique_id = "mwa_debug_buckets"

    @property
    def native_value(self):
        data = self.coordinator.data or []
        return len(data)

    @property
    def extra_state_attributes(self):
        return {
            "entries": self.coordinator.data or []
        }


class MWAEnergyTotalSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    def __init__(self, coordinator):
        _LOGGER.warning("MWA SENSOR INIT CALLED")
        _LOGGER.warning("MWA COORDINATOR PASSED IN: %s", coordinator)
        super().__init__(coordinator)
        _LOGGER.warning("MWA COORDINATOR ON SELF: %s", self.coordinator)
        self._attr_name = "mywateradvisor_Water_Usage_Total"
        self._attr_unique_id = "mywateradvisor_water_total"  # bump for clean start
        self._attr_native_unit_of_measurement = "gal"
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self._total = 0.0
        self._last_timestamp = None

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

        _LOGGER.warning(
            "MWA RESTORE: total=%s last_timestamp=%s",
            self._total,
            self._last_timestamp,
        )
        self.async_write_ha_state()       

    @property
    def native_value(self):
        data = self.coordinator.data

        if data:
            self._process_new_data(data)

        return round(self._total, 2)

    @property
    def extra_state_attributes(self):
        return {
            "last_timestamp": self._last_timestamp
        }

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
                _LOGGER.warning(
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

                _LOGGER.warning(
                    "MWA ADD: ts=%s added=%s total=%s",
                    ts_str,
                    val,
                    self._total,
                )

                # advance cursor immediately
                self._last_timestamp = ts_str

    async def async_update(self):
        _LOGGER.warning("MWA ASYNC UPDATE CALLED")

        data = self.coordinator.data

        if not data:
            _LOGGER.warning("MWA NO DATA")
            return

        self._process_new_data(data)
