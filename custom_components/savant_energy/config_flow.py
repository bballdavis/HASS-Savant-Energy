# custom_components/savant_energy/config_flow.py
"""Config flow for Savant Energy integration."""

from __future__ import annotations

import logging
import traceback
from typing import Any

import voluptuous as vol  # type: ignore

from homeassistant import config_entries  # type: ignore
from homeassistant.core import callback  # type: ignore
from homeassistant.helpers import selector  # type: ignore

from .const import (
    AUTH_INFLUX_SSH,
    CONF_ADDRESS,
    CONF_CIRCUIT_MAP,
    CONF_DMX_TESTING_MODE,
    CONF_HOST,
    CONF_INFLUX_AUTH_METHOD,
    CONF_INFLUX_BUCKET,
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
    DEFAULT_INFLUX_BUCKET,
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
from .influx_client import discover_circuit_metadata_with_backfill
from .influx_org_resolver import InfluxOrgCandidate, async_discover_influx_org
from .ssh_helper import (
    InfluxHostMetadata,
    InfluxTokenCandidate,
    async_ssh_bootstrap,
    async_ssh_install_and_verify_key,
    async_ssh_prepare_bootstrap,
    async_ssh_prepare_bootstrap_candidates,
)
from .legacy.snapshot_data import fetch_current_energy_snapshot

_LOGGER = logging.getLogger(__name__)
_CIRCUIT_MAP_WARNING_NOTIFICATION_ID = f"{DOMAIN}_circuit_map_reconfigure_warning"


async def _async_safe_ssh_bootstrap(hass, host: str, username: str, password: str):
    """Translate unexpected SSH pipeline errors without exposing credentials."""
    try:
        return await async_ssh_bootstrap(hass, host, username, password)
    except Exception:
        trace = traceback.format_exc()
        for secret in (password, host, username):
            if secret:
                trace = trace.replace(secret, "[redacted]")
        _LOGGER.error("SSH setup stage failed unexpectedly (setup_unexpected): %s", trace)
        return None, None, None, "setup_unexpected"


async def _async_safe_ssh_prepare_bootstrap(hass, host: str, username: str, password: str):
    """Read and prepare SSH credentials without mutating the host."""
    try:
        return await async_ssh_prepare_bootstrap(hass, host, username, password)
    except Exception:
        trace = traceback.format_exc()
        for secret in (password, host, username):
            if secret:
                trace = trace.replace(secret, "[redacted]")
        _LOGGER.error("SSH preparation failed unexpectedly (setup_unexpected): %s", trace)
        return None, None, None, None, "setup_unexpected"


async def _async_safe_ssh_prepare_bootstrap_candidates(hass, host: str, username: str, password: str):
    """Enumerate SSH token candidates without selecting one by path order."""
    try:
        return await async_ssh_prepare_bootstrap_candidates(hass, host, username, password)
    except Exception:
        _LOGGER.exception("SSH candidate enumeration failed (setup_unexpected)")
        return None, None, [], "setup_unexpected"


async def _async_safe_ssh_install_and_verify_key(
    hass,
    host: str,
    username: str,
    password: str,
    private_key: str,
    public_key: str,
    token: str,
) -> str | None:
    """Translate unexpected key-install errors without exposing credentials."""
    try:
        return await async_ssh_install_and_verify_key(
            hass,
            host,
            username,
            password,
            private_key,
            public_key,
            token,
        )
    except Exception:
        trace = traceback.format_exc()
        for secret in (password, host, username, private_key, public_key, token):
            if secret:
                trace = trace.replace(secret, "[redacted]")
        _LOGGER.error("SSH key installation failed unexpectedly (setup_unexpected): %s", trace)
        return "setup_unexpected"


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
    return {candidate_key: candidate.summary for candidate_key, candidate in candidates.items()}


def _candidate_key(candidate: InfluxOrgCandidate) -> str:
    """Return a stable selector value that keeps same-org buckets distinct."""
    return f"{candidate.org_id}::{candidate.selected_bucket or DEFAULT_INFLUX_BUCKET}"


def _format_circuit_map_warning_message(warnings: list[str]) -> str:
    """Build a user-facing warning for downgraded relay candidates."""
    intro = (
        "Savant Energy completed reconfigure, but one or more circuits could not be "
        "mapped confidently to a Savant relay UID. Those circuits were saved as "
        "CT/read-only sensors so energy monitoring stays available."
    )
    if not warnings:
        return intro

    listed = "\n".join(f"- {warning}" for warning in warnings[:10])
    return f"{intro}\n\nDowngraded circuits:\n{listed}"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for Savant Energy."""

    VERSION = 4

    _pending: dict[str, Any]

    def __init__(self) -> None:
        self._pending = {}
        self._pending_org_candidates: dict[str, InfluxOrgCandidate] = {}
        self._pending_circuit_map_warnings: list[str] = []
        self._pending_ssh_bootstrap: dict[str, str] | None = None
        self._pending_ssh_error: str | None = None

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
            CONF_INFLUX_BUCKET: self._pending.get(
                CONF_INFLUX_BUCKET,
                current.get(CONF_INFLUX_BUCKET, DEFAULT_INFLUX_BUCKET),
            ),
            CONF_CIRCUIT_MAP: self._pending.get(
                CONF_CIRCUIT_MAP,
                current.get(CONF_CIRCUIT_MAP, {}),
            ),
            CONF_SSH_PRIVATE_KEY: self._pending.get(
                CONF_SSH_PRIVATE_KEY,
                current.get(CONF_SSH_PRIVATE_KEY, ""),
            ),
        }

    def _remember_org_candidates(self, candidates: list[InfluxOrgCandidate]) -> None:
        self._pending_org_candidates = {_candidate_key(candidate): candidate for candidate in candidates}

    def _remember_ssh_bootstrap(
        self,
        host: str,
        password: str,
        private_key: str,
        public_key: str,
        token: str,
    ) -> None:
        self._pending_ssh_bootstrap = {
            "host": host,
            "password": password,
            "private_key": private_key,
            "public_key": public_key,
            "token": token,
        }

    async def _async_install_pending_ssh_key(self) -> str | None:
        bootstrap = self._pending_ssh_bootstrap
        if not bootstrap:
            return None
        error_key = await _async_safe_ssh_install_and_verify_key(
            self.hass,
            bootstrap["host"],
            DEFAULT_SSH_USERNAME,
            bootstrap["password"],
            bootstrap["private_key"],
            bootstrap["public_key"],
            bootstrap["token"],
        )
        if error_key is None:
            self._pending[CONF_SSH_PRIVATE_KEY] = bootstrap["private_key"]
            self._pending_ssh_bootstrap = None
        return error_key

    def _reset_stale_direct_token_pending(self) -> None:
        """Discard resumable direct-token flow state before restarting SSH."""
        for key in (CONF_INFLUX_TOKEN, CONF_INFLUX_ORG, CONF_INFLUX_BUCKET, CONF_CIRCUIT_MAP):
            self._pending.pop(key, None)
        self._pending_org_candidates = {}
        self._pending_ssh_bootstrap = None
        self._pending_ssh_error = None
        self._pending[CONF_INFLUX_AUTH_METHOD] = AUTH_INFLUX_SSH

    async def _async_discover_pending_org(
        self,
        host_metadata: InfluxHostMetadata | None = None,
    ) -> tuple[str | None, str | None]:
        """Resolve the best org for the currently pending host/token pair."""
        _LOGGER.debug(
            "Discovering pending Influx org for host=%s url=%s metadata=%s",
            self._pending.get(CONF_HOST, "<unset>"),
            self._resolve_pending_influx_url(),
            bool(host_metadata and (host_metadata.org_id or host_metadata.bucket_name)),
        )
        result = await async_discover_influx_org(
            self._resolve_pending_influx_url(),
            self._pending[CONF_INFLUX_TOKEN],
            host_metadata,
        )
        if result.selected_org_id:
            _LOGGER.info(
                "Pending Influx org discovery selected %s from %d candidate(s)",
                result.selected_org_id,
                len(result.candidates),
            )
            self._pending[CONF_INFLUX_ORG] = result.selected_org_id
            self._pending[CONF_INFLUX_BUCKET] = result.selected_bucket or DEFAULT_INFLUX_BUCKET
            self._pending_org_candidates = {}
            return result.selected_org_id, None
        if result.candidates:
            _LOGGER.debug(
                "Pending Influx org discovery returned %d candidate(s): %s",
                len(result.candidates),
                "; ".join(candidate.summary for candidate in result.candidates[:5]),
            )
            self._remember_org_candidates(result.candidates)
            return None, "select"
        _LOGGER.debug(
            "Pending Influx org discovery failed with %s: %s",
            result.error_key or "<unset>",
            result.error_message or "<no message>",
        )
        return None, result.error_key or "org_discovery_failed"

    async def _async_safe_discover_pending_org(
        self, host_metadata: InfluxHostMetadata | None = None
    ) -> tuple[str | None, str | None]:
        try:
            return await self._async_discover_pending_org(host_metadata)
        except Exception:
            trace = traceback.format_exc()
            token = str(self._pending.get(CONF_INFLUX_TOKEN, ""))
            if token:
                trace = trace.replace(token, "[redacted]")
            _LOGGER.error("Influx token setup stage failed unexpectedly (setup_unexpected): %s", trace)
            return None, "setup_unexpected"

    async def _async_select_ssh_token_candidate(
        self, candidates: list[InfluxTokenCandidate]
    ) -> tuple[InfluxTokenCandidate | None, str | None]:
        """Validate candidates end-to-end before allowing one into pending state.

        Org discovery itself performs host-metadata/direct bucket queries when
        `/api/v2/orgs` is empty; the circuit query makes the final selection a
        real Savant data validation rather than a path-order preference.
        """
        original = {
            key: self._pending.get(key)
            for key in (CONF_INFLUX_TOKEN, CONF_INFLUX_ORG, CONF_INFLUX_BUCKET, CONF_CIRCUIT_MAP)
        }
        last_error = "ssh_token_empty"
        for candidate in candidates:
            self._pending[CONF_INFLUX_TOKEN] = candidate.token
            for key in (CONF_INFLUX_ORG, CONF_INFLUX_BUCKET, CONF_CIRCUIT_MAP):
                self._pending.pop(key, None)
            _org, outcome = await self._async_safe_discover_pending_org(candidate.metadata)
            if outcome == "select":
                # The candidate has a real data discovery result but needs a
                # user org choice. Retain it for the existing selection step.
                return candidate, outcome
            if outcome is None:
                circuit_error = await self._async_discover_pending_circuit_map()
                if circuit_error is None:
                    return candidate, None
                last_error = circuit_error
            else:
                last_error = outcome
        for key, value in original.items():
            if value is None:
                self._pending.pop(key, None)
            else:
                self._pending[key] = value
        return None, last_error

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

    async def _async_discover_pending_circuit_map(self) -> str | None:
        """Resolve the persisted circuit map for the pending current-mode config."""
        self._pending_circuit_map_warnings = []
        try:
            result = await discover_circuit_metadata_with_backfill(
                self._resolve_pending_influx_url(),
                self._pending[CONF_INFLUX_TOKEN],
                self._pending[CONF_INFLUX_ORG],
                sem_host=self._pending[CONF_ADDRESS],
                influx_bucket=self._pending.get(CONF_INFLUX_BUCKET, DEFAULT_INFLUX_BUCKET),
            )
        except Exception:
            trace = traceback.format_exc()
            token = str(self._pending.get(CONF_INFLUX_TOKEN, ""))
            if token:
                trace = trace.replace(token, "[redacted]")
            _LOGGER.error("Influx circuit setup stage failed unexpectedly (setup_unexpected): %s", trace)
            return "setup_unexpected"
        if result.success and result.circuit_map:
            warnings = list(result.warnings or [])
            entry = self._get_reconfigure_entry() if self.context.get("entry_id") else None
            existing_map = dict((entry.data if entry else {}).get(CONF_CIRCUIT_MAP, {}) or {})
            discovered_keys = set(result.circuit_map)
            missing_existing_keys = sorted(set(existing_map) - discovered_keys)
            if missing_existing_keys:
                # A partial reconfigure response cannot prove that an already
                # mapped circuit was removed. Preserve the complete stored
                # identity map instead of replacing it with a smaller map.
                self._pending[CONF_CIRCUIT_MAP] = existing_map
                warnings.append(
                    "Circuit inventory was incomplete; preserved the existing circuit map "
                    f"({len(missing_existing_keys)} stored circuit(s) were absent from discovery)."
                )
                _LOGGER.warning(
                    "Reconfigure discovery omitted %d stored circuit(s); preserving existing map",
                    len(missing_existing_keys),
                )
            else:
                self._pending[CONF_CIRCUIT_MAP] = result.circuit_map
            self._pending_circuit_map_warnings = warnings
            return None
        _LOGGER.warning(
            "Current-mode circuit discovery failed for %s via %s: %s",
            self._pending.get(CONF_ADDRESS, "<unset>"),
            result.query_window or "<unset>",
            result.error_message or result.error_key or "<no details>",
        )
        return result.error_key or "circuit_discovery_failed"

    async def _async_finish_pending_manual_org(self, org_id: str, bucket: str = DEFAULT_INFLUX_BUCKET) -> str | None:
        """Validate an explicitly supplied org ID through the normal circuit query."""
        self._pending[CONF_INFLUX_ORG] = org_id
        self._pending[CONF_INFLUX_BUCKET] = bucket.strip() or DEFAULT_INFLUX_BUCKET
        return await self._async_discover_pending_circuit_map()

    async def _async_update_circuit_map_warning_notification(self) -> None:
        """Create or clear the reconfigure warning notification."""
        warnings = self._pending_circuit_map_warnings
        if warnings:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Savant Energy Reconfigure Completed With Warnings",
                    "message": _format_circuit_map_warning_message(warnings),
                    "notification_id": _CIRCUIT_MAP_WARNING_NOTIFICATION_ID,
                },
                blocking=True,
            )
            return

        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": _CIRCUIT_MAP_WARNING_NOTIFICATION_ID},
            blocking=True,
        )

    async def _async_finish_current_setup(self):
        """Create the new current-mode entry from pending values."""
        _LOGGER.debug(
            "Finishing current setup with org=%s url=%s token=%s ssh_key=%s",
            self._pending.get(CONF_INFLUX_ORG, "<unset>"),
            self._resolve_pending_influx_url(),
            bool(self._pending.get(CONF_INFLUX_TOKEN)),
            bool(self._pending.get(CONF_SSH_PRIVATE_KEY)),
        )
        await self._async_update_circuit_map_warning_notification()
        return self.async_create_entry(
            title="Savant Energy",
            data=self._build_current_data(),
        )

    async def _async_finish_current_reconfigure(self, config_entry):
        """Persist current-mode data changes and reload the entry."""
        _LOGGER.debug(
            "Finishing reconfigure for entry %s with org=%s url=%s token=%s ssh_key=%s",
            config_entry.entry_id,
            self._pending.get(CONF_INFLUX_ORG, config_entry.data.get(CONF_INFLUX_ORG, "<unset>")),
            self._resolve_pending_influx_url(),
            bool(self._pending.get(CONF_INFLUX_TOKEN)),
            bool(self._pending.get(CONF_SSH_PRIVATE_KEY)),
        )
        self.hass.config_entries.async_update_entry(
            config_entry,
            data=self._build_current_data(config_entry.data),
        )
        await self.hass.config_entries.async_reload(config_entry.entry_id)
        await self._async_update_circuit_map_warning_notification()
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
                self._pending[CONF_INFLUX_AUTH_METHOD] = AUTH_INFLUX_SSH
                return await self.async_step_current_ssh()

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
        """Compatibility route for old flow state; active setup is SSH-only."""
        self._pending[CONF_INFLUX_AUTH_METHOD] = AUTH_INFLUX_SSH
        return await self.async_step_current_ssh()

    async def async_step_current_token(self, user_input=None):
        """Safely redirect stale pasted-token flow state to SSH bootstrap."""
        self._reset_stale_direct_token_pending()
        return await self.async_step_current_ssh()

    async def async_step_current_ssh(self, user_input=None):
        """Current mode step 3b: SSH password (used once) to install key and fetch token."""
        errors = {}
        if self._pending_ssh_error:
            errors[CONF_SSH_PASSWORD] = self._pending_ssh_error
            self._pending_ssh_error = None
        if user_input is not None:
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            if not ssh_password:
                errors[CONF_SSH_PASSWORD] = "required"
            else:
                private_key, public_key, candidates, error_key = await _async_safe_ssh_prepare_bootstrap_candidates(
                    self.hass, self._pending[CONF_HOST], DEFAULT_SSH_USERNAME, ssh_password
                )
                if error_key:
                    errors[CONF_SSH_PASSWORD] = error_key
                else:
                    selected, outcome = await self._async_select_ssh_token_candidate(candidates)
                    if selected and outcome is None:
                        self._remember_ssh_bootstrap(
                            self._pending[CONF_HOST],
                            ssh_password,
                            private_key,
                            public_key,
                            selected.token,
                        )
                        install_error = await self._async_install_pending_ssh_key()
                        if install_error is None:
                            return await self._async_finish_current_setup()
                        errors[CONF_SSH_PASSWORD] = install_error
                    elif selected and outcome == "select":
                        self._remember_ssh_bootstrap(
                            self._pending[CONF_HOST],
                            ssh_password,
                            private_key,
                            public_key,
                            selected.token,
                        )
                        return await self.async_step_current_org_select()
                    elif "base" not in errors:
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
            candidate_key = user_input.get(CONF_INFLUX_ORG)
            if candidate_key not in self._pending_org_candidates:
                errors["base"] = "org_selection_required"
            else:
                candidate = self._pending_org_candidates[candidate_key]
                self._pending[CONF_INFLUX_ORG] = candidate.org_id
                self._pending[CONF_INFLUX_BUCKET] = candidate.selected_bucket or DEFAULT_INFLUX_BUCKET
                circuit_error = await self._async_discover_pending_circuit_map()
                if circuit_error is None:
                    install_error = await self._async_install_pending_ssh_key()
                    if install_error is None:
                        self._pending_org_candidates = {}
                        return await self._async_finish_current_setup()
                    self._pending_ssh_error = install_error
                    return await self.async_step_current_ssh()
                else:
                    errors["base"] = circuit_error

        return self.async_show_form(
            step_id="current_org_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_INFLUX_ORG): vol.In(_candidate_options(self._pending_org_candidates))}
            ),
            errors=errors,
        )

    async def async_step_current_org_manual(self, user_input=None):
        """Safely redirect stale manual-org flow state to SSH bootstrap."""
        self._reset_stale_direct_token_pending()
        return await self.async_step_current_ssh()

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
                self._pending[CONF_INFLUX_AUTH_METHOD] = AUTH_INFLUX_SSH
                return await self.async_step_current_ssh()

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
                # Do not mutate the entry here. The existing token/auth state
                # remains active until SSH candidate validation and key install
                # have completed successfully.
                self._pending[CONF_INFLUX_AUTH_METHOD] = AUTH_INFLUX_SSH
                return await self.async_step_reconfigure_ssh()

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
        """Compatibility route for old flow state; active reconfigure is SSH-only."""
        self._pending[CONF_INFLUX_AUTH_METHOD] = AUTH_INFLUX_SSH
        return await self.async_step_reconfigure_ssh()

    async def async_step_reconfigure_token(self, user_input=None):
        """Safely redirect stale pasted-token reconfigure state to SSH bootstrap."""
        self._reset_stale_direct_token_pending()
        return await self.async_step_reconfigure_ssh()

    async def async_step_reconfigure_ssh(self, user_input=None):
        """Reconfigure current step 3b: SSH password (used once) to install key and fetch token."""
        config_entry = self._get_reconfigure_entry()
        errors = {}
        if self._pending_ssh_error:
            errors[CONF_SSH_PASSWORD] = self._pending_ssh_error
            self._pending_ssh_error = None
        if user_input is not None:
            ssh_password = (user_input.get(CONF_SSH_PASSWORD) or "").strip()
            if not ssh_password:
                errors[CONF_SSH_PASSWORD] = "required"
            else:
                private_key, public_key, candidates, error_key = await _async_safe_ssh_prepare_bootstrap_candidates(
                    self.hass, self._pending[CONF_HOST], DEFAULT_SSH_USERNAME, ssh_password
                )
                if error_key:
                    errors[CONF_SSH_PASSWORD] = error_key
                else:
                    selected, outcome = await self._async_select_ssh_token_candidate(candidates)
                    if selected and outcome is None:
                        self._remember_ssh_bootstrap(
                            self._pending[CONF_HOST],
                            ssh_password,
                            private_key,
                            public_key,
                            selected.token,
                        )
                        install_error = await self._async_install_pending_ssh_key()
                        if install_error is None:
                            return await self._async_finish_current_reconfigure(config_entry)
                        errors[CONF_SSH_PASSWORD] = install_error
                    elif selected and outcome == "select":
                        self._remember_ssh_bootstrap(
                            self._pending[CONF_HOST],
                            ssh_password,
                            private_key,
                            public_key,
                            selected.token,
                        )
                        return await self.async_step_reconfigure_org_select()
                    elif "base" not in errors:
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
            candidate_key = user_input.get(CONF_INFLUX_ORG)
            if candidate_key not in self._pending_org_candidates:
                errors["base"] = "org_selection_required"
            else:
                candidate = self._pending_org_candidates[candidate_key]
                self._pending[CONF_INFLUX_ORG] = candidate.org_id
                self._pending[CONF_INFLUX_BUCKET] = candidate.selected_bucket or DEFAULT_INFLUX_BUCKET
                circuit_error = await self._async_discover_pending_circuit_map()
                if circuit_error is None:
                    install_error = await self._async_install_pending_ssh_key()
                    if install_error is None:
                        self._pending_org_candidates = {}
                        return await self._async_finish_current_reconfigure(config_entry)
                    self._pending_ssh_error = install_error
                    return await self.async_step_reconfigure_ssh()
                else:
                    errors["base"] = circuit_error

        return self.async_show_form(
            step_id="reconfigure_org_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_INFLUX_ORG): vol.In(_candidate_options(self._pending_org_candidates))}
            ),
            errors=errors,
        )

    async def async_step_reconfigure_org_manual(self, user_input=None):
        """Safely redirect stale manual-org reconfigure state to SSH bootstrap."""
        self._reset_stale_direct_token_pending()
        return await self.async_step_reconfigure_ssh()

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
                host = self.config_entry.data.get(CONF_HOST, "")
                if not host:
                    errors[CONF_SSH_PASSWORD] = "host_not_available"
                else:
                    private_key, public_key, token_candidates, error_key = await _async_safe_ssh_prepare_bootstrap_candidates(
                        self.hass, host, DEFAULT_SSH_USERNAME, ssh_password
                    )
                    if error_key:
                        errors[CONF_SSH_PASSWORD] = error_key
                    else:
                        selected = None
                        chosen_org = None
                        chosen_bucket = None
                        last_error = "org_discovery_failed"
                        url = self.config_entry.data.get(CONF_INFLUX_URL, _derive_influx_url(host))
                        current_org = self.config_entry.data.get(CONF_INFLUX_ORG, "")
                        for candidate_token in token_candidates:
                            try:
                                result = await async_discover_influx_org(url, candidate_token.token, candidate_token.metadata)
                            except Exception:
                                last_error = "setup_unexpected"
                                continue
                            candidate_org = result.selected_org_id
                            candidate_bucket = result.selected_bucket
                            if candidate_org is None and result.candidates and current_org:
                                matching = [candidate for candidate in result.candidates if candidate.org_id == current_org]
                                if matching:
                                    match = max(matching, key=lambda item: item.score)
                                    candidate_org, candidate_bucket = current_org, match.selected_bucket
                            if not candidate_org:
                                last_error = "org_reconfigure_required" if result.candidates else (result.error_key or last_error)
                                continue
                            circuit_result = await discover_circuit_metadata_with_backfill(
                                url, candidate_token.token, candidate_org,
                                sem_host=self.config_entry.data.get(CONF_ADDRESS, ""),
                                influx_bucket=candidate_bucket or DEFAULT_INFLUX_BUCKET,
                            )
                            if circuit_result.success and circuit_result.circuit_map:
                                selected, chosen_org, chosen_bucket = candidate_token, candidate_org, candidate_bucket
                                break
                            last_error = circuit_result.error_key or "circuit_discovery_failed"
                        if selected is None:
                            errors["base"] = last_error
                        else:
                            install_error = await _async_safe_ssh_install_and_verify_key(
                                self.hass,
                                host,
                                DEFAULT_SSH_USERNAME,
                                ssh_password,
                                private_key,
                                public_key,
                                selected.token,
                            )
                            if install_error:
                                errors[CONF_SSH_PASSWORD] = install_error
                                return self.async_show_form(
                                    step_id="reprovision_ssh",
                                    data_schema=vol.Schema({vol.Required(CONF_SSH_PASSWORD): str}),
                                    errors=errors,
                                )
                            data = dict(self.config_entry.data)
                            data[CONF_INFLUX_TOKEN] = selected.token
                            data[CONF_SSH_PRIVATE_KEY] = private_key
                            data[CONF_INFLUX_ORG] = chosen_org
                            data[CONF_INFLUX_BUCKET] = (
                                chosen_bucket
                                or data.get(CONF_INFLUX_BUCKET)
                                or DEFAULT_INFLUX_BUCKET
                            )
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
