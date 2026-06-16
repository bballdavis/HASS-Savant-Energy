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
    AUTH_INFLUX_SSH,
    AUTH_INFLUX_TOKEN,
    CONF_ADDRESS,
    CONF_DMX_TESTING_MODE,
    CONF_HOST,
    CONF_INFLUX_AUTH_METHOD,
    CONF_INFLUX_ORG,
    CONF_INFLUX_TOKEN,
    CONF_INFLUX_URL,
    CONF_MODE,
    CONF_OLA_PORT,
    CONF_PENDING_CONFIRM_MULTIPLIER,
    CONF_SCAN_INTERVAL,
    CONF_SSH_PASSWORD,
    CONF_SSH_PRIVATE_KEY,
    CONF_SWITCH_COOLDOWN,
    DEFAULT_DMX_TESTING_MODE,
    DEFAULT_DISABLE_SCENE_BUILDER,
    DEFAULT_INFLUX_AUTH_METHOD,
    DEFAULT_INFLUX_ORG,
    DEFAULT_MODE,
    DEFAULT_OLA_PORT,
    DEFAULT_PENDING_CONFIRM_MULTIPLIER,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSH_USERNAME,
    DEFAULT_SWITCH_COOLDOWN,
    DOMAIN,
    MODE_AUTO,
    MODE_CURRENT,
    MODE_LEGACY,
    SCAN_INTERVAL_OPTIONS,
)
from .influx_org_resolver import InfluxOrgCandidate, async_discover_influx_org
from .legacy.snapshot_data import fetch_current_energy_snapshot

_LOGGER = logging.getLogger(__name__)


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


def _candidate_options(candidates: dict[str, InfluxOrgCandidate]) -> dict[str, str]:
    return {org_id: candidate.summary for org_id, candidate in candidates.items()}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for Savant Energy."""

    VERSION = 4

    _pending: dict[str, Any]

    def __init__(self) -> None:
        self._pending = {}
        self._pending_org_candidates: dict[str, InfluxOrgCandidate] = {}

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
        """Build entry data for current mode, preserving existing non-option values."""
        current = dict(base or {})
        host_ip = self._pending[CONF_HOST]
        current_url = current.get(CONF_INFLUX_URL)
        current_host = current.get(CONF_HOST, "")
        derived_current_url = _derive_influx_url(current_host) if current_host else ""
        influx_url = (
            current_url
            if current_url and current_url != derived_current_url
            else _derive_influx_url(host_ip)
        )
        return {
            CONF_OLA_PORT: current.get(CONF_OLA_PORT, DEFAULT_OLA_PORT),
            CONF_SCAN_INTERVAL: current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_DMX_TESTING_MODE: current.get(CONF_DMX_TESTING_MODE, DEFAULT_DMX_TESTING_MODE),
            "disable_scene_builder": current.get("disable_scene_builder", DEFAULT_DISABLE_SCENE_BUILDER),
            **current,
            CONF_MODE: MODE_CURRENT,
            CONF_ADDRESS: self._pending[CONF_ADDRESS],
            CONF_HOST: host_ip,
            CONF_INFLUX_AUTH_METHOD: self._pending.get(
                CONF_INFLUX_AUTH_METHOD,
                current.get(CONF_INFLUX_AUTH_METHOD, DEFAULT_INFLUX_AUTH_METHOD),
            ),
            CONF_INFLUX_URL: influx_url,
            CONF_INFLUX_TOKEN: self._pending[CONF_INFLUX_TOKEN],
            CONF_INFLUX_ORG: self._pending.get(
                CONF_INFLUX_ORG,
                current.get(CONF_INFLUX_ORG, DEFAULT_INFLUX_ORG),
            ),
            CONF_SSH_PRIVATE_KEY: self._pending.get(
                CONF_SSH_PRIVATE_KEY,
                current.get(CONF_SSH_PRIVATE_KEY, ""),
            ),
        }

    def _remember_org_candidates(self, candidates: list[InfluxOrgCandidate]) -> None:
        self._pending_org_candidates = {candidate.org_id: candidate for candidate in candidates}

    async def _async_discover_pending_org(self) -> tuple[str | None, str | None]:
        """Resolve the best org for the currently pending host/token pair."""
        result = await async_discover_influx_org(
            self._resolve_pending_influx_url(),
            self._pending[CONF_INFLUX_TOKEN],
        )
        if result.selected_org_id:
            self._pending[CONF_INFLUX_ORG] = result.selected_org_id
            self._pending_org_candidates = {}
            return result.selected_org_id, None
        if result.candidates:
            self._remember_org_candidates(result.candidates)
            return None, "select"
        return None, result.error_key or "org_discovery_failed"

    def _resolve_pending_influx_url(self) -> str:
        """Return the best URL for discovery and persistence."""
        entry = self._get_reconfigure_entry() if self.context.get("entry_id") else None
        base = entry.data if entry else {}
        current = dict(base or {})
        host_ip = self._pending.get(CONF_HOST, current.get(CONF_HOST, ""))
        current_url = current.get(CONF_INFLUX_URL)
        current_host = current.get(CONF_HOST, "")
        derived_current_url = _derive_influx_url(current_host) if current_host else ""
        if current_url and current_url != derived_current_url:
            return current_url
        return _derive_influx_url(host_ip)

    async def _async_finish_current_setup(self):
        """Create the new current-mode entry from pending values."""
        return self.async_create_entry(
            title="Savant Energy",
            data=self._build_current_data(),
        )

    async def _async_finish_current_reconfigure(self, config_entry):
        """Persist current-mode data changes and reload the entry."""
        self.hass.config_entries.async_update_entry(
            config_entry,
            data=self._build_current_data(config_entry.data),
        )
        await self.hass.config_entries.async_reload(config_entry.entry_id)
        return self.async_abort(reason="reconfigure_successful")

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
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS, default="192.168.1.14"): str}),
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
                    vol.Required(CONF_ADDRESS, default=self._pending.get(CONF_ADDRESS, "192.168.1.108")): str,
                    vol.Required(CONF_HOST, default=self._pending.get(CONF_HOST, "192.168.1.14")): str,
                }
            ),
            errors=errors,
        )

    async def async_step_current_auth(self, user_input=None):
        """Current mode step 2: choose how to provide the Influx token."""
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
                _, outcome = await self._async_discover_pending_org()
                if outcome is None:
                    return await self._async_finish_current_setup()
                if outcome == "select":
                    return await self.async_step_current_org_select()
                errors["base"] = outcome

        return self.async_show_form(
            step_id="current_token",
            data_schema=vol.Schema({vol.Required(CONF_INFLUX_TOKEN, default=""): str}),
            errors=errors,
        )

    async def async_step_current_ssh(self, user_input=None):
        """Current mode step 3b: SSH password (used once) to install key and fetch token."""
        errors = {}
        if user_input is not None:
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            if not ssh_password:
                errors[CONF_SSH_PASSWORD] = "required"
            else:
                from .ssh_helper import async_ssh_bootstrap

                private_key, token, error_key = await async_ssh_bootstrap(
                    self.hass, self._pending[CONF_HOST], DEFAULT_SSH_USERNAME, ssh_password
                )
                if error_key:
                    errors[CONF_SSH_PASSWORD] = error_key
                else:
                    self._pending[CONF_INFLUX_TOKEN] = token
                    self._pending[CONF_SSH_PRIVATE_KEY] = private_key
                    _, outcome = await self._async_discover_pending_org()
                    if outcome is None:
                        return await self._async_finish_current_setup()
                    if outcome == "select":
                        return await self.async_step_current_org_select()
                    errors["base"] = outcome

        return self.async_show_form(
            step_id="current_ssh",
            data_schema=vol.Schema({vol.Required(CONF_SSH_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_current_org_select(self, user_input=None):
        """Select a discovered Influx organization during initial setup."""
        errors = {}
        if user_input is not None:
            org_id = user_input.get(CONF_INFLUX_ORG)
            if org_id not in self._pending_org_candidates:
                errors["base"] = "org_selection_required"
            else:
                self._pending[CONF_INFLUX_ORG] = org_id
                self._pending_org_candidates = {}
                return await self._async_finish_current_setup()

        return self.async_show_form(
            step_id="current_org_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_INFLUX_ORG): vol.In(_candidate_options(self._pending_org_candidates))}
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
                {vol.Required(CONF_ADDRESS, default=self._pending.get(CONF_ADDRESS, "192.168.1.108")): str}
            ),
            errors=errors,
        )

    async def async_step_auto_current_host(self, user_input=None):
        """Auto fallback: legacy feed not found, enter Host IP then continue to auth."""
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
            data_schema=vol.Schema({vol.Required(CONF_HOST, default="192.168.1.14"): str}),
            errors=errors,
        )

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
                            CONF_INFLUX_AUTH_METHOD,
                            DEFAULT_INFLUX_AUTH_METHOD,
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
                _, outcome = await self._async_discover_pending_org()
                if outcome is None:
                    return await self._async_finish_current_reconfigure(config_entry)
                if outcome == "select":
                    return await self.async_step_reconfigure_org_select()
                errors["base"] = outcome

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
        """Reconfigure current step 3b: SSH password (used once) to install key and fetch token."""
        config_entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            if not ssh_password:
                errors[CONF_SSH_PASSWORD] = "required"
            else:
                from .ssh_helper import async_ssh_bootstrap

                private_key, token, error_key = await async_ssh_bootstrap(
                    self.hass, self._pending[CONF_HOST], DEFAULT_SSH_USERNAME, ssh_password
                )
                if error_key:
                    errors[CONF_SSH_PASSWORD] = error_key
                else:
                    self._pending[CONF_INFLUX_TOKEN] = token
                    self._pending[CONF_SSH_PRIVATE_KEY] = private_key
                    _, outcome = await self._async_discover_pending_org()
                    if outcome is None:
                        return await self._async_finish_current_reconfigure(config_entry)
                    if outcome == "select":
                        return await self.async_step_reconfigure_org_select()
                    errors["base"] = outcome

        return self.async_show_form(
            step_id="reconfigure_ssh",
            data_schema=vol.Schema({vol.Required(CONF_SSH_PASSWORD): str}),
            errors=errors,
        )

    async def async_step_reconfigure_org_select(self, user_input=None):
        """Select a discovered Influx organization during reconfigure."""
        config_entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            org_id = user_input.get(CONF_INFLUX_ORG)
            if org_id not in self._pending_org_candidates:
                errors["base"] = "org_selection_required"
            else:
                self._pending[CONF_INFLUX_ORG] = org_id
                self._pending_org_candidates = {}
                return await self._async_finish_current_reconfigure(config_entry)

        return self.async_show_form(
            step_id="reconfigure_org_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_INFLUX_ORG): vol.In(_candidate_options(self._pending_org_candidates))}
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
    """Options flow: tunable settings without editing connection credentials."""

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
                reprovision = user_input.pop("reprovision_ssh_key", False)
                if reprovision:
                    self._pending_options = user_input
                    return await self.async_step_reprovision_ssh()
                return self.async_create_entry(title="", data=user_input)

        def _opt(key, default):
            return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

        has_key = bool(self.config_entry.data.get(CONF_SSH_PRIVATE_KEY, ""))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
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
                    vol.Optional("reprovision_ssh_key", default=False): bool,
                }
            ),
            description_placeholders={
                "ssh_key_status": "installed" if has_key else "not configured",
            },
            errors=errors,
        )

    async def async_step_reprovision_ssh(self, user_input=None):
        """Re-bootstrap the SSH key using a fresh password."""
        errors = {}
        if user_input is not None:
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            if not ssh_password:
                errors[CONF_SSH_PASSWORD] = "required"
            else:
                from .ssh_helper import async_ssh_bootstrap

                host = self.config_entry.data.get(CONF_HOST, "")
                if not host:
                    errors[CONF_SSH_PASSWORD] = "host_not_available"
                else:
                    private_key, token, error_key = await async_ssh_bootstrap(
                        self.hass, host, DEFAULT_SSH_USERNAME, ssh_password
                    )
                    if error_key:
                        errors[CONF_SSH_PASSWORD] = error_key
                    else:
                        result = await async_discover_influx_org(
                            self.config_entry.data.get(CONF_INFLUX_URL, _derive_influx_url(host)),
                            token,
                        )
                        chosen_org = result.selected_org_id
                        current_org = self.config_entry.data.get(CONF_INFLUX_ORG, "")
                        if chosen_org is None and result.candidates and current_org:
                            if any(candidate.org_id == current_org for candidate in result.candidates):
                                chosen_org = current_org

                        if chosen_org is None:
                            errors["base"] = (
                                "org_reconfigure_required"
                                if result.candidates
                                else (result.error_key or "org_discovery_failed")
                            )
                        else:
                            data = dict(self.config_entry.data)
                            data[CONF_INFLUX_TOKEN] = token
                            data[CONF_SSH_PRIVATE_KEY] = private_key
                            data[CONF_INFLUX_ORG] = chosen_org
                            self.hass.config_entries.async_update_entry(
                                self.config_entry,
                                data=data,
                            )
                            return self.async_create_entry(
                                title="",
                                data=getattr(self, "_pending_options", {}),
                            )

        return self.async_show_form(
            step_id="reprovision_ssh",
            data_schema=vol.Schema({vol.Required(CONF_SSH_PASSWORD): str}),
            errors=errors,
        )
