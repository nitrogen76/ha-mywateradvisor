from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from datetime import timedelta
import logging

from .api import fetch_data  # your existing API function

DOMAIN = "mywateradvisor"
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(hass, entry):
    username = entry.data["username"]
    password = entry.data["password"]

    async def async_update_data():
        _LOGGER.warning("MWA FETCH CALLED")
        return await hass.async_add_executor_job(fetch_data, username, password)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="mywateradvisor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # This connects sensor.py
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass, entry):
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
