import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_TIME_RAW_MODE,
    DEFAULT_TIME_RAW_MODE,
    TIME_RAW_MODES,
    CONF_ENABLE_DEBUG_SENSOR,
    CONF_MAX_REASONABLE_HOURLY_CONS,
    CONF_SKIP_NEGATIVE_CORRECTIONS,
    DEFAULT_ENABLE_DEBUG_SENSOR,
    DEFAULT_MAX_REASONABLE_HOURLY_CONS,
    DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
    DOMAIN,
)


class MyWaterAdvisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MyWaterAdvisorOptionsFlow()

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            time_raw_mode = user_input.pop(
                CONF_TIME_RAW_MODE, DEFAULT_TIME_RAW_MODE
            )
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
                    CONF_TIME_RAW_MODE: time_raw_mode,
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
                    CONF_TIME_RAW_MODE, default=DEFAULT_TIME_RAW_MODE
                ): vol.In(TIME_RAW_MODES),
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
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        time_raw_mode = self.config_entry.options.get(
            CONF_TIME_RAW_MODE,
            self.config_entry.data.get(CONF_TIME_RAW_MODE, DEFAULT_TIME_RAW_MODE),
        )
        enable_debug_sensor = self.config_entry.options.get(
            CONF_ENABLE_DEBUG_SENSOR,
            self.config_entry.data.get(
                CONF_ENABLE_DEBUG_SENSOR,
                DEFAULT_ENABLE_DEBUG_SENSOR,
            ),
        )
        max_reasonable_hourly_cons = self.config_entry.options.get(
            CONF_MAX_REASONABLE_HOURLY_CONS,
            self.config_entry.data.get(
                CONF_MAX_REASONABLE_HOURLY_CONS,
                DEFAULT_MAX_REASONABLE_HOURLY_CONS,
            ),
        )
        skip_negative_corrections = self.config_entry.options.get(
            CONF_SKIP_NEGATIVE_CORRECTIONS,
            self.config_entry.data.get(
                CONF_SKIP_NEGATIVE_CORRECTIONS,
                DEFAULT_SKIP_NEGATIVE_CORRECTIONS,
            ),
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TIME_RAW_MODE, default=time_raw_mode
                ): vol.In(TIME_RAW_MODES),
                vol.Optional(
                    CONF_ENABLE_DEBUG_SENSOR,
                    default=enable_debug_sensor,
                ): bool,
                vol.Optional(
                    CONF_MAX_REASONABLE_HOURLY_CONS,
                    default=max_reasonable_hourly_cons,
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Optional(
                    CONF_SKIP_NEGATIVE_CORRECTIONS,
                    default=skip_negative_corrections,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
