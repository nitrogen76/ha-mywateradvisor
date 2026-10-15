from datetime import timedelta

DOMAIN = "mywateradvisor"

CONF_TIME_RAW_MODE = "time_raw_mode"
DEFAULT_TIME_RAW_MODE = "utc"
TIME_RAW_MODES = {"utc": "UTC", "local": "Local"}

CONF_ENABLE_DEBUG_SENSOR = "enable_debug_sensor"
CONF_MAX_REASONABLE_HOURLY_CONS = "max_reasonable_hourly_cons"
CONF_SKIP_NEGATIVE_CORRECTIONS = "skip_negative_corrections"

DEFAULT_ENABLE_DEBUG_SENSOR = False
DEFAULT_MAX_REASONABLE_HOURLY_CONS = 2000.0
DEFAULT_SKIP_NEGATIVE_CORRECTIONS = True

HOURLY_LOOKBACK_DAYS = 7
STORAGE_VERSION = 1

SCAN_INTERVAL = timedelta(minutes=30)
