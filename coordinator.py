import logging

import requests
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import fetch_data
from .const import DOMAIN, SCAN_INTERVAL


class MyWaterAdvisorDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(
                fetch_data,
                self.entry.data["username"],
                self.entry.data["password"],
            )
        except requests.HTTPError as err:
            status = getattr(err.response, "status_code", None)
            if status in (401, 403):
                raise ConfigEntryAuthFailed from err

            raise
