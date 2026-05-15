from datetime import timedelta

DOMAIN = "mywateradvisor"

CONF_ENABLE_DEBUG_SENSOR = "enable_debug_sensor"
CONF_MAX_REASONABLE_HOURLY_CONS = "max_reasonable_hourly_cons"
CONF_SKIP_NEGATIVE_CORRECTIONS = "skip_negative_corrections"

DEFAULT_ENABLE_DEBUG_SENSOR = False
DEFAULT_MAX_REASONABLE_HOURLY_CONS = 2000.0
DEFAULT_SKIP_NEGATIVE_CORRECTIONS = True

SCAN_INTERVAL = timedelta(minutes=30)
