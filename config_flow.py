import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ENABLE_DEBUG_SENSOR,
    CONF_MAX_REASONABLE_HOURLY_CONS,
    CONF_SKIP_NEGATIVE_CORRECTIONS,
    DEFAULT_ENABLE_DEBUG_SENSOR,
    DEFAULT_MAX_REASONABLE_HOURLY_CONS,
    DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
    DOMAIN,
)


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_ENABLE_DEBUG_SENSOR,
            default=DEFAULT_ENABLE_DEBUG_SENSOR,
        ): bool,
        vol.Optional(
            CONF_MAX_REASONABLE_HOURLY_CONS,
            default=DEFAULT_MAX_REASONABLE_HOURLY_CONS,
        ): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(
            CONF_SKIP_NEGATIVE_CORRECTIONS,
            default=DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
        ): bool,
    }
)


class MyWaterAdvisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MyWaterAdvisorOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            enable_debug_sensor = user_input.pop(
                CONF_ENABLE_DEBUG_SENSOR,
                DEFAULT_ENABLE_DEBUG_SENSOR,
            )
            max_reasonable_hourly_cons = user_input.pop(
                CONF_MAX_REASONABLE_HOURLY_CONS,
                DEFAULT_MAX_REASONABLE_HOURLY_CONS,
            )
            skip_negative_corrections = user_input.pop(
                CONF_SKIP_NEGATIVE_CORRECTIONS,
                DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
            )
            return self.async_create_entry(
                title="MyWaterAdvisor",
                data=user_input,
                options={
                    CONF_ENABLE_DEBUG_SENSOR: enable_debug_sensor,
                    CONF_MAX_REASONABLE_HOURLY_CONS: max_reasonable_hourly_cons,
                    CONF_SKIP_NEGATIVE_CORRECTIONS: skip_negative_corrections,
                },
            )

        schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional(
                    CONF_ENABLE_DEBUG_SENSOR,
                    default=DEFAULT_ENABLE_DEBUG_SENSOR,
                ): bool,
                vol.Optional(
                    CONF_MAX_REASONABLE_HOURLY_CONS,
                    default=DEFAULT_MAX_REASONABLE_HOURLY_CONS,
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Optional(
                    CONF_SKIP_NEGATIVE_CORRECTIONS,
                    default=DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )


class MyWaterAdvisorOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        config_entry = getattr(self, "config_entry", self._config_entry)
        suggested_values = {
            CONF_ENABLE_DEBUG_SENSOR: config_entry.options.get(
                CONF_ENABLE_DEBUG_SENSOR,
                config_entry.data.get(
                    CONF_ENABLE_DEBUG_SENSOR,
                    DEFAULT_ENABLE_DEBUG_SENSOR,
                ),
            ),
            CONF_MAX_REASONABLE_HOURLY_CONS: config_entry.options.get(
                CONF_MAX_REASONABLE_HOURLY_CONS,
                config_entry.data.get(
                    CONF_MAX_REASONABLE_HOURLY_CONS,
                    DEFAULT_MAX_REASONABLE_HOURLY_CONS,
                ),
            ),
            CONF_SKIP_NEGATIVE_CORRECTIONS: config_entry.options.get(
                CONF_SKIP_NEGATIVE_CORRECTIONS,
                config_entry.data.get(
                    CONF_SKIP_NEGATIVE_CORRECTIONS,
                    DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
                ),
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                suggested_values,
            ),
        )
