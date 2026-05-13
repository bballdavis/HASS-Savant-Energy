"""Constants for the Savant Energy integration.
Defines all configuration keys, defaults, and branding info used throughout the integration.
All constants are now documented for clarity and open source maintainability.
"""

# Domain name for the integration
DOMAIN = "savant_energy"

# List of Home Assistant platforms supported by this integration
PLATFORMS = ["sensor", "binary_sensor", "switch", "button"]

# Dispatcher signals
SIGNAL_DMX_DISCOVERY_COMPLETE = "savant_energy_dmx_discovery_complete"

# Configuration keys
CONF_ADDRESS = "address"          # IP address of Savant controller (used for OLA/DMX relay control)
CONF_HOST = "host"                # Host IP for InfluxDB access (current >=11.2 mode)
CONF_MODE = "mode"                # Integration mode: legacy/current/auto
CONF_PORT = "port"                # Legacy TCP snapshot port (no longer used for data; kept for compat)
CONF_OLA_PORT = "ola_port"        # Port for OLA/DMX relay control API
CONF_SCAN_INTERVAL = "scan_interval"  # InfluxDB poll interval (seconds)
CONF_SWITCH_COOLDOWN = "switch_cooldown"  # Minimum seconds between relay toggles
CONF_DMX_TESTING_MODE = "dmx_testing_mode"  # Enable advanced DMX testing mode
CONF_INFLUX_AUTH_METHOD = "influx_auth_method"  # Choose token or SSH-based token fetch

CONF_PENDING_CONFIRM_MULTIPLIER = "pending_confirm_multiplier"

# InfluxDB configuration keys
CONF_INFLUX_URL = "influx_url"    # InfluxDB base URL, e.g. http://192.168.1.14:8086
CONF_INFLUX_TOKEN = "influx_token"  # InfluxDB read token
CONF_INFLUX_ORG = "influx_org"    # InfluxDB org ID

# Default values
DEFAULT_SWITCH_COOLDOWN = 15  # seconds
DEFAULT_PORT = 2000           # legacy TCP snapshot port
DEFAULT_OLA_PORT = 9090       # OLA/DMX API port
DEFAULT_SEM_COMPANION_PORT = 8644
DEFAULT_SCAN_INTERVAL = 5     # seconds between InfluxDB polls
DEFAULT_INFLUX_URL = "http://192.168.1.14:8086"
DEFAULT_INFLUX_ORG = ""

MODE_LEGACY = "legacy"
MODE_CURRENT = "current"
MODE_AUTO = "auto"
DEFAULT_MODE = MODE_AUTO

# Boolean config defaults
DEFAULT_DMX_TESTING_MODE = False
DEFAULT_DISABLE_SCENE_BUILDER = False
DEFAULT_PENDING_CONFIRM_MULTIPLIER = 2

AUTH_INFLUX_TOKEN = "token"
AUTH_INFLUX_SSH = "ssh"
DEFAULT_INFLUX_AUTH_METHOD = AUTH_INFLUX_TOKEN

# Scan interval choices shown in the UI (seconds)
SCAN_INTERVAL_OPTIONS = [5, 10, 15, 30]

# Manufacturer branding
MANUFACTURER = "Savant"
