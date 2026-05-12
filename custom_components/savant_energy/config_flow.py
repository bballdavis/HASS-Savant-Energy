# custom_components/savant_energy/config_flow.py
"""Config flow for Savant Energy integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol  # type: ignore

from homeassistant import config_entries  # type: ignore
from homeassistant.core import callback  # type: ignore
from homeassistant.helpers import selector  # type: ignore

from .const import (
    DOMAIN,
    CONF_ADDRESS,
    CONF_HOST,
    CONF_MODE,
    CONF_OLA_PORT,
    CONF_SCAN_INTERVAL,
    CONF_INFLUX_URL,
    CONF_INFLUX_TOKEN,
    CONF_INFLUX_ORG,
    CONF_SWITCH_COOLDOWN,
    CONF_PENDING_CONFIRM_MULTIPLIER,
    CONF_DMX_TESTING_MODE,
    DEFAULT_MODE,
    MODE_LEGACY,
    MODE_CURRENT,
    MODE_AUTO,
    DEFAULT_PORT,
    DEFAULT_OLA_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SWITCH_COOLDOWN,
    DEFAULT_INFLUX_URL,
    DEFAULT_INFLUX_ORG,
    DEFAULT_DMX_TESTING_MODE,
    DEFAULT_DISABLE_SCENE_BUILDER,
    DEFAULT_PENDING_CONFIRM_MULTIPLIER,
    SCAN_INTERVAL_OPTIONS,
)
from .legacy.snapshot_data import fetch_current_energy_snapshot

_LOGGER = logging.getLogger(__name__)

CONF_SSH_PASSWORD = "ssh_password"


def _derive_influx_url(host: str) -> str:
    return f"http://{host.strip()}:8086"


def _mode_selector(include_auto: bool = True):
    options = [MODE_LEGACY, MODE_CURRENT, MODE_AUTO] if include_auto else [MODE_LEGACY, MODE_CURRENT]
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key="mode",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


async def _fetch_influx_token_via_ssh(hass, host: str, password: str) -> str | None:
    """Retrieve InfluxDB token from Savant host over SSH.

    Uses paramiko when available. Returns None on any failure.
    """
    try:
        import paramiko  # type: ignore
    except Exception:
        _LOGGER.warning("paramiko not available; cannot auto-fetch Influx token")
        return None

    def _worker() -> str | None:
        client = None
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, username="RPM", password=password, timeout=10)
            _stdin, stdout, _stderr = client.exec_command(
                "cat /home/RPM/.remote/rpm_modules/rpm-energy/current/influxdb/read.token"
            )
            token = stdout.read().decode("utf-8", errors="ignore").strip()
            return token or None
        except Exception as exc:
            _LOGGER.warning("Failed to fetch Influx token via SSH from %s: %s", host, exc)
            return None
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    return await hass.async_add_executor_job(_worker)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for Savant Energy."""

    VERSION = 3

    _pending: dict[str, Any]

    def __init__(self) -> None:
        self._pending = {}

    async def async_step_user(self, user_input=None):
        """Initial setup: choose operating mode."""
        errors = {}
        if user_input is not None:
            mode = user_input.get(CONF_MODE, DEFAULT_MODE)
            self._pending[CONF_MODE] = mode
            if mode == MODE_LEGACY:
                return await self.async_step_legacy_setup()
            if mode == MODE_CURRENT:
                return await self.async_step_current_setup()
            return await self.async_step_auto_probe()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE, default=DEFAULT_MODE): _mode_selector(include_auto=True)
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_legacy_setup(self, user_input=None):
        """Configure legacy (<11.2) mode."""
        errors = {}
        if user_input is not None:
            if not self._valid_address(user_input.get(CONF_ADDRESS)):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                data = {
                    CONF_MODE: MODE_LEGACY,
                    CONF_ADDRESS: user_input[CONF_ADDRESS].strip(),
                    CONF_OLA_PORT: DEFAULT_OLA_PORT,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_DMX_TESTING_MODE: DEFAULT_DMX_TESTING_MODE,
                    "disable_scene_builder": DEFAULT_DISABLE_SCENE_BUILDER,
                }
                return self.async_create_entry(title="Savant Energy", data=data)

        return self.async_show_form(
            step_id="legacy_setup",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default="192.168.1.14"): str,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_current_setup(self, user_input=None):
        """Configure current (>=11.2) mode."""
        errors = {}
        if user_input is not None:
            pbc_ip = (user_input.get(CONF_ADDRESS) or "").strip()
            host_ip = (user_input.get(CONF_HOST) or "").strip()
            token = (user_input.get(CONF_INFLUX_TOKEN) or "").strip()
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()

            if not self._valid_address(pbc_ip):
                errors[CONF_ADDRESS] = "invalid_address"
            elif not self._valid_address(host_ip):
                errors[CONF_HOST] = "invalid_address"
            else:
                if not token and ssh_password:
                    token = await _fetch_influx_token_via_ssh(self.hass, host_ip, ssh_password) or ""
                if not token:
                    errors[CONF_INFLUX_TOKEN] = "required"
                else:
                    data = {
                        CONF_MODE: MODE_CURRENT,
                        CONF_ADDRESS: pbc_ip,
                        CONF_HOST: host_ip,
                        CONF_INFLUX_URL: _derive_influx_url(host_ip),
                        CONF_INFLUX_TOKEN: token,
                        CONF_INFLUX_ORG: DEFAULT_INFLUX_ORG,
                        CONF_OLA_PORT: DEFAULT_OLA_PORT,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_DMX_TESTING_MODE: DEFAULT_DMX_TESTING_MODE,
                        "disable_scene_builder": DEFAULT_DISABLE_SCENE_BUILDER,
                    }
                    return self.async_create_entry(title="Savant Energy", data=data)

        return self.async_show_form(
            step_id="current_setup",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default=self._pending.get(CONF_ADDRESS, "192.168.1.108")): str,
                    vol.Required(CONF_HOST, default="192.168.1.14"): str,
                    vol.Optional(CONF_INFLUX_TOKEN, default=""): str,
                    vol.Optional(CONF_SSH_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_auto_probe(self, user_input=None):
        """Auto mode: probe for legacy activity feed first."""
        errors = {}
        if user_input is not None:
            pbc_ip = (user_input.get(CONF_ADDRESS) or "").strip()
            if not self._valid_address(pbc_ip):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                self._pending[CONF_ADDRESS] = pbc_ip
                probe_result = await self.hass.async_add_executor_job(
                    fetch_current_energy_snapshot,
                    pbc_ip,
                    DEFAULT_PORT,
                )
                if probe_result.success:
                    data = {
                        CONF_MODE: MODE_LEGACY,
                        CONF_ADDRESS: pbc_ip,
                        CONF_OLA_PORT: DEFAULT_OLA_PORT,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_DMX_TESTING_MODE: DEFAULT_DMX_TESTING_MODE,
                        "disable_scene_builder": DEFAULT_DISABLE_SCENE_BUILDER,
                    }
                    return self.async_create_entry(title="Savant Energy", data=data)
                return await self.async_step_auto_current_fallback()

        return self.async_show_form(
            step_id="auto_probe",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default=self._pending.get(CONF_ADDRESS, "192.168.1.108")): str,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_auto_current_fallback(self, user_input=None):
        """Auto mode fallback to current setup when legacy feed is unavailable."""
        errors = {}
        if user_input is not None:
            host_ip = (user_input.get(CONF_HOST) or "").strip()
            token = (user_input.get(CONF_INFLUX_TOKEN) or "").strip()
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            pbc_ip = self._pending.get(CONF_ADDRESS, "")

            if not self._valid_address(host_ip):
                errors[CONF_HOST] = "invalid_address"
            else:
                if not token and ssh_password:
                    token = await _fetch_influx_token_via_ssh(self.hass, host_ip, ssh_password) or ""
                if not token:
                    errors[CONF_INFLUX_TOKEN] = "required"
                else:
                    data = {
                        CONF_MODE: MODE_CURRENT,
                        CONF_ADDRESS: pbc_ip,
                        CONF_HOST: host_ip,
                        CONF_INFLUX_URL: _derive_influx_url(host_ip),
                        CONF_INFLUX_TOKEN: token,
                        CONF_INFLUX_ORG: DEFAULT_INFLUX_ORG,
                        CONF_OLA_PORT: DEFAULT_OLA_PORT,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_DMX_TESTING_MODE: DEFAULT_DMX_TESTING_MODE,
                        "disable_scene_builder": DEFAULT_DISABLE_SCENE_BUILDER,
                    }
                    return self.async_create_entry(title="Savant Energy", data=data)

        return self.async_show_form(
            step_id="auto_current_fallback",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default="192.168.1.14"): str,
                    vol.Optional(CONF_INFLUX_TOKEN, default=""): str,
                    vol.Optional(CONF_SSH_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_reconfigure(self, user_input=None):
        """Allow updating mode and credentials after setup."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id")
        )
        errors = {}
        if user_input is not None:
            mode = user_input.get(CONF_MODE, config_entry.data.get(CONF_MODE, MODE_LEGACY))
            pbc_ip = (user_input.get(CONF_ADDRESS) or "").strip()
            host_ip = (user_input.get(CONF_HOST) or "").strip()
            token = (user_input.get(CONF_INFLUX_TOKEN) or "").strip()
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()

            if not self._valid_address(pbc_ip):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                update = {
                    CONF_MODE: mode,
                    CONF_ADDRESS: pbc_ip,
                    CONF_OLA_PORT: config_entry.data.get(CONF_OLA_PORT, DEFAULT_OLA_PORT),
                }

                if mode == MODE_CURRENT:
                    if not self._valid_address(host_ip):
                        errors[CONF_HOST] = "invalid_address"
                    else:
                        if not token and ssh_password:
                            token = await _fetch_influx_token_via_ssh(self.hass, host_ip, ssh_password) or ""
                        if not token:
                            errors[CONF_INFLUX_TOKEN] = "required"
                        else:
                            update.update(
                                {
                                    CONF_HOST: host_ip,
                                    CONF_INFLUX_URL: _derive_influx_url(host_ip),
                                    CONF_INFLUX_TOKEN: token,
                                    CONF_INFLUX_ORG: config_entry.data.get(
                                        CONF_INFLUX_ORG,
                                        DEFAULT_INFLUX_ORG,
                                    ),
                                }
                            )

                if errors:
                    return self.async_show_form(
                        step_id="reconfigure",
                        data_schema=self._reconfigure_schema(config_entry),
                        errors=errors,
                        description_placeholders={},
                    )

                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data={**config_entry.data, **update},
                )
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._reconfigure_schema(config_entry),
            errors=errors,
            description_placeholders={},
        )

    def _reconfigure_schema(self, config_entry):
        return vol.Schema(
            {
                vol.Required(
                    CONF_MODE,
                    default=config_entry.data.get(CONF_MODE, MODE_LEGACY),
                ): _mode_selector(include_auto=False),
                vol.Required(
                    CONF_ADDRESS,
                    default=config_entry.data.get(CONF_ADDRESS, "192.168.1.108"),
                ): str,
                vol.Optional(
                    CONF_HOST,
                    default=config_entry.data.get(CONF_HOST, "192.168.1.14"),
                ): str,
                vol.Optional(
                    CONF_INFLUX_TOKEN,
                    default=config_entry.data.get(CONF_INFLUX_TOKEN, ""),
                ): str,
                vol.Optional(CONF_SSH_PASSWORD, default=""): str,
            }
        )

    @staticmethod
    def _valid_address(address) -> bool:
        return bool(address and str(address).strip())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow: tunable settings without re-entering credentials."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                pcm = int(
                    user_input.get(
                        CONF_PENDING_CONFIRM_MULTIPLIER,
                        DEFAULT_PENDING_CONFIRM_MULTIPLIER,
                    )
                )
                if not 1 <= pcm <= 10:
                    errors[CONF_PENDING_CONFIRM_MULTIPLIER] = "out_of_range"
            except (TypeError, ValueError):
                errors[CONF_PENDING_CONFIRM_MULTIPLIER] = "invalid_value"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        def _opt(key, default):
            return self.config_entry.options.get(
                key, self.config_entry.data.get(key, default)
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default=_opt(CONF_ADDRESS, "192.168.1.14")): str,
                    vol.Optional(CONF_HOST, default=_opt(CONF_HOST, "192.168.1.14")): str,
                    vol.Required(
                        CONF_MODE,
                        default=_opt(CONF_MODE, MODE_LEGACY),
                    ): _mode_selector(include_auto=False),
                    vol.Required(CONF_INFLUX_URL, default=_opt(CONF_INFLUX_URL, DEFAULT_INFLUX_URL)): str,
                    vol.Required(CONF_INFLUX_TOKEN, default=_opt(CONF_INFLUX_TOKEN, "")): str,
                    vol.Required(CONF_INFLUX_ORG, default=_opt(CONF_INFLUX_ORG, DEFAULT_INFLUX_ORG)): str,
                    vol.Required(CONF_OLA_PORT, default=_opt(CONF_OLA_PORT, DEFAULT_OLA_PORT)): int,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=_opt(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.In(SCAN_INTERVAL_OPTIONS),
                    vol.Optional(
                        CONF_SWITCH_COOLDOWN,
                        default=_opt(CONF_SWITCH_COOLDOWN, DEFAULT_SWITCH_COOLDOWN),
                    ): int,
                    vol.Required(
                        CONF_PENDING_CONFIRM_MULTIPLIER,
                        default=_opt(
                            CONF_PENDING_CONFIRM_MULTIPLIER,
                            DEFAULT_PENDING_CONFIRM_MULTIPLIER,
                        ),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_DMX_TESTING_MODE,
                        default=_opt(CONF_DMX_TESTING_MODE, DEFAULT_DMX_TESTING_MODE),
                    ): bool,
                    vol.Optional(
                        "disable_scene_builder",
                        default=_opt("disable_scene_builder", DEFAULT_DISABLE_SCENE_BUILDER),
                    ): bool,
                }
            ),
            errors=errors,
            description_placeholders={},
        )
