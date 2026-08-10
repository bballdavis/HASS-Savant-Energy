"""Helpers for normalizing Savant Energy config-entry storage."""

from __future__ import annotations

from .const import (
    CONF_ADDRESS,
    CONF_CIRCUIT_MAP,
    CONF_HOST,
    CONF_INFLUX_AUTH_METHOD,
    CONF_INFLUX_BUCKET,
    CONF_INFLUX_ORG,
    CONF_INFLUX_TOKEN,
    CONF_INFLUX_URL,
    CONF_MODE,
    CONF_OLA_PORT,
    CONF_SSH_PRIVATE_KEY,
    DEFAULT_INFLUX_ORG,
    DEFAULT_INFLUX_BUCKET,
    MODE_CURRENT,
    MODE_LEGACY,
)

_ENTRY_DATA_KEYS = (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_MODE,
    CONF_OLA_PORT,
    CONF_INFLUX_AUTH_METHOD,
    CONF_INFLUX_URL,
    CONF_INFLUX_TOKEN,
    CONF_INFLUX_ORG,
    CONF_INFLUX_BUCKET,
    CONF_CIRCUIT_MAP,
    CONF_SSH_PRIVATE_KEY,
)


def normalize_entry_storage(data: dict | None, options: dict | None) -> tuple[dict, dict, bool]:
    """Move connection/auth state out of options and into data."""
    normalized_data = dict(data or {})
    normalized_options = dict(options or {})
    changed = False

    if CONF_MODE not in normalized_data:
        normalized_data[CONF_MODE] = MODE_LEGACY
        changed = True

    for key in _ENTRY_DATA_KEYS:
        if key in normalized_options:
            value = normalized_options.pop(key)
            if key not in normalized_data or normalized_data.get(key) in (None, "", DEFAULT_INFLUX_ORG):
                normalized_data[key] = value
            changed = True

    if normalized_data.get(CONF_MODE) == MODE_CURRENT:
        if not str(normalized_data.get(CONF_INFLUX_BUCKET, "")).strip():
            normalized_data[CONF_INFLUX_BUCKET] = DEFAULT_INFLUX_BUCKET
            changed = True
        host = normalized_data.get(CONF_HOST, normalized_data.get(CONF_ADDRESS, ""))
        if host and not normalized_data.get(CONF_INFLUX_URL):
            normalized_data[CONF_INFLUX_URL] = f"http://{host}:8086"
            changed = True

    return normalized_data, normalized_options, changed
