"""Sensor platform for the MyWaterAdvisor integration.

The API now exposes one cumulative reading for the current UTC month. Home
Assistant derives consumption from successive increases in that value, so this
platform deliberately does not reconstruct hourly buckets.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_DEBUG_SENSOR, DEFAULT_ENABLE_DEBUG_SENSOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up MyWaterAdvisor sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [MWAWaterUsageTotalSensor(coordinator, entry)]

    if entry.options.get(
        CONF_ENABLE_DEBUG_SENSOR,
        entry.data.get(CONF_ENABLE_DEBUG_SENSOR, DEFAULT_ENABLE_DEBUG_SENSOR),
    ):
        entities.append(MWADebugSensor(coordinator, entry))

    async_add_entities(entities)


def device_info(entry) -> dict[str, Any]:
    """Return device metadata shared by all entities."""
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "MyWaterAdvisor",
        "manufacturer": "MyWaterAdvisor",
    }


class MWADebugSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic view of the raw cumulative value returned by the coordinator."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:water-check"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_name = "MWA Debug Monthly Reading"
        self._attr_unique_id = f"{entry.entry_id}_mwa_debug_monthly_reading"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> float | None:
        """Return the coordinator's raw monthly reading."""
        value = self.coordinator.data
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose basic coordinator diagnostics."""
        return {
            "last_update_success": self.coordinator.last_update_success,
            "raw_value": self.coordinator.data,
        }


class MWAWaterUsageTotalSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Current-month cumulative water consumption."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:water"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)

        # Preserve the old name and unique ID so the existing entity should keep
        # its registry identity, dashboards, history, and automations.
        self._attr_name = "mywateradvisor_Water_Usage_Total"
        self._attr_unique_id = f"{entry.entry_id}_mywateradvisor_water_total"
        self._attr_device_info = device_info(entry)

        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return the last valid cumulative monthly reading."""
        return self._value

    @property
    def available(self) -> bool:
        """Remain available when a zero reading was intentionally ignored.

        A failed coordinator refresh is still reported unavailable. An explicit
        zero from the API becomes ``None`` in api.py and leaves the last valid
        value untouched.
        """
        return self.coordinator.last_update_success and self._value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the source model for troubleshooting."""
        return {
            "source": "current_utc_month_cumulative",
            "zero_readings_ignored": True,
        }

    def _process_new_data(self, value: Any) -> None:
        """Accept one valid positive cumulative reading.

        ``None`` means api.py deliberately ignored a zero response, so retain
        the previous value rather than creating a false reset in statistics.
        """
        if value is None:
            _LOGGER.debug(
                "MWA monthly reading was None; retaining previous value %s",
                self._value,
            )
            return

        try:
            new_value = round(float(value), 1)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Invalid MyWaterAdvisor monthly reading %r; retaining %s",
                value,
                self._value,
            )
            return

        if new_value <= 0:
            _LOGGER.warning(
                "Non-positive MyWaterAdvisor monthly reading %s ignored; "
                "retaining %s",
                new_value,
                self._value,
            )
            return

        self._value = new_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process a coordinator refresh."""
        self._process_new_data(self.coordinator.data)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last valid reading, then apply current coordinator data."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                restored = float(last_state.state)
                if restored > 0:
                    self._value = round(restored, 1)
            except (TypeError, ValueError):
                _LOGGER.warning(
                    "Unable to restore MyWaterAdvisor state %r",
                    last_state.state,
                )

        self._process_new_data(self.coordinator.data)
        self.async_write_ha_state()
