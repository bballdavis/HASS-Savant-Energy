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
    CONF_INFLUX_AUTH_METHOD,
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
    DEFAULT_INFLUX_AUTH_METHOD,
    AUTH_INFLUX_TOKEN,
    AUTH_INFLUX_SSH,
    SCAN_INTERVAL_OPTIONS,
)
from .legacy.snapshot_data import fetch_current_energy_snapshot

_LOGGER = logging.getLogger(__name__)

CONF_SSH_PASSWORD = "ssh_password"


def _auth_method_selector():
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[AUTH_INFLUX_TOKEN, AUTH_INFLUX_SSH],
            translation_key="influx_auth_method",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


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


async def _fetch_influx_token_via_ssh(
    hass, host: str, password: str
) -> tuple[str | None, str | None]:
    """Retrieve the InfluxDB read token from a Savant host over SSH.

    All blocking I/O (including the paramiko import) runs on the executor thread.
    Returns (token, None) on success or (None, error_key) on failure so callers
    can surface a specific error message in the config UI.
    """
    def _worker() -> tuple[str | None, str | None]:
        try:
            import paramiko  # type: ignore  # noqa: PLC0415
        except Exception as exc:
            _LOGGER.warning("paramiko unavailable — SSH token fetch not possible: %s", exc)
            return None, "ssh_unavailable"

        client = None
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, username="RPM", password=password, timeout=10)
            _stdin, stdout, _stderr = client.exec_command(
                "cat /data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken"
            )
            token = stdout.read().decode("utf-8", errors="ignore").strip()
            if not token:
                _LOGGER.warning("SSH connected to %s but token file was empty or missing", host)
                return None, "ssh_token_empty"
            return token, None
        except Exception as exc:
            _LOGGER.warning("SSH token fetch from %s failed: %s", host, exc)
            return None, "ssh_failed"
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

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_reconfigure_entry(self):
        return self.hass.config_entries.async_get_entry(self.context.get("entry_id"))

    def _build_legacy_data(self, base: dict | None = None) -> dict:
        """Build entry data for legacy mode, preserving any existing settings."""
        return {
            CONF_OLA_PORT: DEFAULT_OLA_PORT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_DMX_TESTING_MODE: DEFAULT_DMX_TESTING_MODE,
            "disable_scene_builder": DEFAULT_DISABLE_SCENE_BUILDER,
            **(base or {}),
            CONF_MODE: MODE_LEGACY,
            CONF_ADDRESS: self._pending[CONF_ADDRESS],
        }

    def _build_current_data(self, base: dict | None = None) -> dict:
        """Build entry data for current mode, preserving any existing settings."""
        host_ip = self._pending[CONF_HOST]
        return {
            CONF_OLA_PORT: DEFAULT_OLA_PORT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_DMX_TESTING_MODE: DEFAULT_DMX_TESTING_MODE,
            "disable_scene_builder": DEFAULT_DISABLE_SCENE_BUILDER,
            CONF_INFLUX_ORG: DEFAULT_INFLUX_ORG,
            **(base or {}),
            CONF_MODE: MODE_CURRENT,
            CONF_ADDRESS: self._pending[CONF_ADDRESS],
            CONF_HOST: host_ip,
            CONF_INFLUX_AUTH_METHOD: self._pending[CONF_INFLUX_AUTH_METHOD],
            CONF_INFLUX_URL: _derive_influx_url(host_ip),
            CONF_INFLUX_TOKEN: self._pending[CONF_INFLUX_TOKEN],
        }

    # ── Initial setup ────────────────────────────────────────────────────────

    async def async_step_user(self, user_input=None):
        """Step 1: choose operating mode."""
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
                {vol.Required(CONF_MODE, default=DEFAULT_MODE): _mode_selector(include_auto=True)}
            ),
        )

    async def async_step_legacy_setup(self, user_input=None):
        """Legacy mode: enter PBC IP."""
        errors = {}
        if user_input is not None:
            pbc_ip = (user_input.get(CONF_ADDRESS) or "").strip()
            if not self._valid_address(pbc_ip):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                self._pending[CONF_ADDRESS] = pbc_ip
                return self.async_create_entry(
                    title="Savant Energy",
                    data=self._build_legacy_data(),
                )

        return self.async_show_form(
            step_id="legacy_setup",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS, default="192.168.1.14"): str}
            ),
            errors=errors,
        )

    async def async_step_current_setup(self, user_input=None):
        """Current mode step 1: enter PBC IP and Host IP."""
        errors = {}
        if user_input is not None:
            pbc_ip = (user_input.get(CONF_ADDRESS) or "").strip()
            host_ip = (user_input.get(CONF_HOST) or "").strip()
            if not self._valid_address(pbc_ip):
                errors[CONF_ADDRESS] = "invalid_address"
            elif not self._valid_address(host_ip):
                errors[CONF_HOST] = "invalid_address"
            else:
                self._pending[CONF_ADDRESS] = pbc_ip
                self._pending[CONF_HOST] = host_ip
                return await self.async_step_current_auth()

        return self.async_show_form(
            step_id="current_setup",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=self._pending.get(CONF_ADDRESS, "192.168.1.108"),
                    ): str,
                    vol.Required(
                        CONF_HOST,
                        default=self._pending.get(CONF_HOST, "192.168.1.14"),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_current_auth(self, user_input=None):
        """Current mode step 2: choose how to provide the Influx token.

        Shared by both the current_setup path and the auto_probe fallback path.
        """
        if user_input is not None:
            auth_method = user_input.get(CONF_INFLUX_AUTH_METHOD, DEFAULT_INFLUX_AUTH_METHOD)
            self._pending[CONF_INFLUX_AUTH_METHOD] = auth_method
            if auth_method == AUTH_INFLUX_SSH:
                return await self.async_step_current_ssh()
            return await self.async_step_current_token()

        return self.async_show_form(
            step_id="current_auth",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INFLUX_AUTH_METHOD,
                        default=DEFAULT_INFLUX_AUTH_METHOD,
                    ): _auth_method_selector()
                }
            ),
        )

    async def async_step_current_token(self, user_input=None):
        """Current mode step 3a: paste an Influx read token."""
        errors = {}
        if user_input is not None:
            token = (user_input.get(CONF_INFLUX_TOKEN) or "").strip()
            if not token:
                errors[CONF_INFLUX_TOKEN] = "required"
            else:
                self._pending[CONF_INFLUX_TOKEN] = token
                return self.async_create_entry(
                    title="Savant Energy",
                    data=self._build_current_data(),
                )

        return self.async_show_form(
            step_id="current_token",
            data_schema=vol.Schema(
                {vol.Required(CONF_INFLUX_TOKEN, default=""): str}
            ),
            errors=errors,
        )

    async def async_step_current_ssh(self, user_input=None):
        """Current mode step 3b: SSH password to auto-fetch the Influx token."""
        errors = {}
        if user_input is not None:
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            if not ssh_password:
                errors[CONF_SSH_PASSWORD] = "required"
            else:
                token, ssh_error = await _fetch_influx_token_via_ssh(
                    self.hass, self._pending[CONF_HOST], ssh_password
                )
                if ssh_error:
                    errors[CONF_SSH_PASSWORD] = ssh_error
                else:
                    self._pending[CONF_INFLUX_TOKEN] = token
                    return self.async_create_entry(
                        title="Savant Energy",
                        data=self._build_current_data(),
                    )

        return self.async_show_form(
            step_id="current_ssh",
            data_schema=vol.Schema(
                {vol.Required(CONF_SSH_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_auto_probe(self, user_input=None):
        """Auto mode: enter PBC IP and probe for legacy activity feed."""
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
                    return self.async_create_entry(
                        title="Savant Energy",
                        data=self._build_legacy_data(),
                    )
                return await self.async_step_auto_current_host()

        return self.async_show_form(
            step_id="auto_probe",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=self._pending.get(CONF_ADDRESS, "192.168.1.108"),
                    ): str
                }
            ),
            errors=errors,
        )

    async def async_step_auto_current_host(self, user_input=None):
        """Auto fallback: legacy feed not found — enter Host IP then continue to auth."""
        errors = {}
        if user_input is not None:
            host_ip = (user_input.get(CONF_HOST) or "").strip()
            if not self._valid_address(host_ip):
                errors[CONF_HOST] = "invalid_address"
            else:
                self._pending[CONF_HOST] = host_ip
                return await self.async_step_current_auth()

        return self.async_show_form(
            step_id="auto_current_host",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default="192.168.1.14"): str}
            ),
            errors=errors,
        )

    # ── Reconfigure flow ────────────────────────────────────────────────────

    async def async_step_reconfigure(self, user_input=None):
        """Reconfigure step 1: choose mode."""
        config_entry = self._get_reconfigure_entry()
        if user_input is not None:
            mode = user_input.get(CONF_MODE, config_entry.data.get(CONF_MODE, MODE_LEGACY))
            self._pending[CONF_MODE] = mode
            if mode == MODE_LEGACY:
                return await self.async_step_reconfigure_legacy()
            return await self.async_step_reconfigure_current_host()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODE,
                        default=config_entry.data.get(CONF_MODE, MODE_LEGACY),
                    ): _mode_selector(include_auto=False)
                }
            ),
        )

    async def async_step_reconfigure_legacy(self, user_input=None):
        """Reconfigure legacy: update PBC IP."""
        config_entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            pbc_ip = (user_input.get(CONF_ADDRESS) or "").strip()
            if not self._valid_address(pbc_ip):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                self._pending[CONF_ADDRESS] = pbc_ip
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data=self._build_legacy_data(config_entry.data),
                )
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_legacy",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=config_entry.data.get(CONF_ADDRESS, "192.168.1.14"),
                    ): str
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_current_host(self, user_input=None):
        """Reconfigure current step 1: update PBC IP and Host IP."""
        config_entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            pbc_ip = (user_input.get(CONF_ADDRESS) or "").strip()
            host_ip = (user_input.get(CONF_HOST) or "").strip()
            if not self._valid_address(pbc_ip):
                errors[CONF_ADDRESS] = "invalid_address"
            elif not self._valid_address(host_ip):
                errors[CONF_HOST] = "invalid_address"
            else:
                self._pending[CONF_ADDRESS] = pbc_ip
                self._pending[CONF_HOST] = host_ip
                return await self.async_step_reconfigure_auth()

        return self.async_show_form(
            step_id="reconfigure_current_host",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=config_entry.data.get(CONF_ADDRESS, "192.168.1.108"),
                    ): str,
                    vol.Required(
                        CONF_HOST,
                        default=config_entry.data.get(CONF_HOST, "192.168.1.14"),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_auth(self, user_input=None):
        """Reconfigure current step 2: choose how to provide the Influx token."""
        config_entry = self._get_reconfigure_entry()
        if user_input is not None:
            auth_method = user_input.get(CONF_INFLUX_AUTH_METHOD, DEFAULT_INFLUX_AUTH_METHOD)
            self._pending[CONF_INFLUX_AUTH_METHOD] = auth_method
            if auth_method == AUTH_INFLUX_SSH:
                return await self.async_step_reconfigure_ssh()
            return await self.async_step_reconfigure_token()

        return self.async_show_form(
            step_id="reconfigure_auth",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INFLUX_AUTH_METHOD,
                        default=config_entry.data.get(
                            CONF_INFLUX_AUTH_METHOD, DEFAULT_INFLUX_AUTH_METHOD
                        ),
                    ): _auth_method_selector()
                }
            ),
        )

    async def async_step_reconfigure_token(self, user_input=None):
        """Reconfigure current step 3a: paste an Influx read token."""
        config_entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            token = (user_input.get(CONF_INFLUX_TOKEN) or "").strip()
            if not token:
                errors[CONF_INFLUX_TOKEN] = "required"
            else:
                self._pending[CONF_INFLUX_TOKEN] = token
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data=self._build_current_data(config_entry.data),
                )
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_token",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INFLUX_TOKEN,
                        default=config_entry.data.get(CONF_INFLUX_TOKEN, ""),
                    ): str
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_ssh(self, user_input=None):
        """Reconfigure current step 3b: SSH password to auto-fetch the Influx token."""
        config_entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            if not ssh_password:
                errors[CONF_SSH_PASSWORD] = "required"
            else:
                token, ssh_error = await _fetch_influx_token_via_ssh(
                    self.hass, self._pending[CONF_HOST], ssh_password
                )
                if ssh_error:
                    errors[CONF_SSH_PASSWORD] = ssh_error
                else:
                    self._pending[CONF_INFLUX_TOKEN] = token
                    self.hass.config_entries.async_update_entry(
                        config_entry,
                        data=self._build_current_data(config_entry.data),
                    )
                    await self.hass.config_entries.async_reload(config_entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_ssh",
            data_schema=vol.Schema(
                {vol.Required(CONF_SSH_PASSWORD): str}
            ),
            errors=errors,
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
        )
