import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "mywateradvisor"
CONF_ENABLE_DEBUG_SENSOR = "enable_debug_sensor"


class MyWaterAdvisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    @staticmethod
    def async_get_options_flow(config_entry):
        return MyWaterAdvisorOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            enable_debug_sensor = user_input.pop(CONF_ENABLE_DEBUG_SENSOR, False)
            return self.async_create_entry(
                title="MyWaterAdvisor",
                data=user_input,
                options={CONF_ENABLE_DEBUG_SENSOR: enable_debug_sensor},
            )

        schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional(CONF_ENABLE_DEBUG_SENSOR, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )


class MyWaterAdvisorOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        enable_debug_sensor = self.config_entry.options.get(
            CONF_ENABLE_DEBUG_SENSOR,
            self.config_entry.data.get(CONF_ENABLE_DEBUG_SENSOR, False),
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLE_DEBUG_SENSOR,
                    default=enable_debug_sensor,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
