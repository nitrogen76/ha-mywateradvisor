"""Display the imported total; hourly external statistics feed the dashboard.

These sensors deliberately have no state_class. Recorder must not generate a
second consumption series at the time delayed readings are received.
"""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_DEBUG_SENSOR, DEFAULT_ENABLE_DEBUG_SENSOR, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [MWAWaterUsageTotalSensor(coordinator, entry)]
    if entry.options.get(CONF_ENABLE_DEBUG_SENSOR,
                         entry.data.get(CONF_ENABLE_DEBUG_SENSOR, DEFAULT_ENABLE_DEBUG_SENSOR)):
        entities.append(MWADebugSensor(coordinator, entry))
    async_add_entities(entities)


def device_info(entry):
    return {"identifiers": {(DOMAIN, entry.entry_id)}, "name": "MyWaterAdvisor",
            "manufacturer": "MyWaterAdvisor"}


class MWAWaterUsageTotalSensor(CoordinatorEntity, SensorEntity):
    """Total of retained utility hours, for display and automations."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_device_class = SensorDeviceClass.WATER
    _attr_icon = "mdi:water"
    _attr_state_class = None

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "mywateradvisor_Water_Usage_Total"
        self._attr_unique_id = f"{entry.entry_id}_mywateradvisor_water_total"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.data["total"]

    @property
    def extra_state_attributes(self):
        return {"source": "hourly_utility_statistics",
                "statistic_id": self.coordinator.statistic_id,
                "latest_hour_start_utc": self.coordinator.data["latest_hour"],
                "time_raw_mode": self.coordinator.time_raw_mode,
                "time_zone": str(self.coordinator.time_zone)}


class MWADebugSensor(MWAWaterUsageTotalSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "MWA Debug Hourly Import"
        self._attr_unique_id = f"{entry.entry_id}_mwa_debug_hourly_import"

    @property
    def native_value(self):
        return self.coordinator.data["fetched_buckets"]

    @property
    def extra_state_attributes(self):
        return {**super().extra_state_attributes, **self.coordinator.data}

    _attr_device_class = None
    _attr_native_unit_of_measurement = None
