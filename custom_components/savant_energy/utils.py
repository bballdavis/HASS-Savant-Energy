"""Utility functions for Savant Energy integration.
Provides DMX, API, and helper routines for the integration.
All utility functions are now documented for clarity and open source maintainability.
"""

import logging
import asyncio
import subprocess
import json
from datetime import datetime
import aiohttp
from typing import List, Dict, Any, Optional, Final, Tuple, Union

from homeassistant.helpers.dispatcher import async_dispatcher_send  # type: ignore

from .const import DEFAULT_OLA_PORT, SIGNAL_DMX_DISCOVERY_COMPLETE

_LOGGER = logging.getLogger(__name__)

# DMX API constants
DMX_ON_VALUE: Final = 255
DMX_OFF_VALUE: Final = 0
DMX_CACHE_SECONDS: Final = 5  # Cache DMX status for 5 seconds
DMX_API_TIMEOUT: Final = 30  # Time in seconds to consider API down
DMX_ADDRESS_CACHE_SECONDS: Final = 3600  # Cache DMX address for 1 hour
UID_INFO_TIMEOUT_SECONDS: Final = 10
RDM_DISCOVERY_TIMEOUT_SECONDS: Final = 90
RDM_DEVICE_NOT_FOUND: Final = "The RDM device could not be found"

# Track API statistics
_dmx_api_stats = {
    "request_count": 0,
    "failure_count": 0,
    "last_successful_call": None,
    "success_rate": 100.0
}

# Class variables to track DMX API status across all instances
_last_successful_api_call: Optional[datetime] = None
_api_failure_count: int = 0
_api_request_count: int = 0

# DMX address cache to minimize API calls
_dmx_address_cache = {}  # Maps DMX UID -> {"address": int, "timestamp": datetime}
_dmx_discovery_notifications = {}  # Maps DMX UID -> last error string
_dmx_last_lookup_error: Dict[str, str] = {}
_pending_discovery_tasks: Dict[Tuple[str, int, int], asyncio.Task] = {}


async def _async_fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Fetch JSON data and return payload, raw text, and error string."""
    try:
        timeout_config = aiohttp.ClientTimeout(total=float(timeout))
        async with session.get(
            url,
            timeout=timeout_config,
            allow_redirects=False,
        ) as response:
            text_response = await response.text()
            if 300 <= response.status < 400:
                redirect_target = response.headers.get("Location") or "(no location provided)"
                error = f"Unexpected redirect HTTP {response.status} to {redirect_target}"
                _LOGGER.warning(
                    "Request to %s returned redirect response: %s, body: %s",
                    url,
                    error,
                    text_response,
                )
                return None, text_response, error
            if response.status != 200:
                error = f"HTTP {response.status}"
                _LOGGER.warning(
                    f"Request to {url} failed with {error}, response: {text_response}"
                )
                return None, text_response, error
            try:
                data = json.loads(text_response)
            except json.JSONDecodeError as json_err:
                error = _classify_non_json_response(
                    response.content_type,
                    text_response,
                    json_err,
                )
                _LOGGER.warning(
                    f"JSON decode error from {url}: {error}. Text: {text_response}"
                )
                return None, text_response, error
            return data, text_response, None
    except asyncio.TimeoutError:
        error = "Transport timeout"
        _LOGGER.warning(f"Network error calling {url}: {error}")
        return None, None, error
    except aiohttp.ClientError as err:
        error = f"Transport error: {type(err).__name__}: {err}"
        _LOGGER.warning(f"Network error calling {url}: {error}")
        return None, None, error
    except Exception as err:
        error = f"Unexpected {type(err).__name__}: {err}"
        _LOGGER.warning(f"Unexpected error calling {url}: {error}")
        return None, None, error


def _classify_non_json_response(
    content_type: str,
    text_response: str,
    json_err: json.JSONDecodeError,
) -> str:
    """Classify a non-JSON HTTP 200 response for DMX/RDM endpoints."""
    response_body = text_response.strip()
    lowered_body = response_body.lower()

    if "usage:" in lowered_body and "uid=[uid]" in lowered_body:
        return "Malformed request: endpoint returned usage page instead of JSON"

    if response_body.startswith("<") or content_type == "text/html":
        return f"Unexpected HTML response instead of JSON ({content_type})"

    return f"Invalid JSON response ({content_type}): {json_err}"


async def _async_notify_channel_issue(
    hass: Optional[Any],
    device_label: str,
    dmx_uid: str,
    universe: int,
    error_message: str,
) -> None:
    """Send a persistent notification about a DMX channel lookup failure."""
    if hass is None:
        return
    notification_id = _dmx_notification_id(dmx_uid)
    message = (
        f"Unable to determine the DMX channel for {device_label} (UID {dmx_uid}) in universe {universe} "
        f"after running RDM discovery. Last error: {error_message}."
    )
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "Savant Energy DMX",
            "message": message,
            "notification_id": notification_id,
        },
        blocking=False,
    )
def _dmx_notification_id(dmx_uid: str) -> str:
    """Build a stable notification id for DMX lookup failures."""
    from .const import DOMAIN  # Local import to avoid circular dependency at import time

    sanitized_uid = slugify(dmx_uid.replace(":", "_"))
    return f"{DOMAIN}_dmx_{sanitized_uid}"


async def _async_clear_channel_issue(
    hass: Optional[Any],
    dmx_uid: str,
) -> None:
    """Dismiss any existing persistent notification for a resolved DMX lookup."""
    if hass is None:
        return

    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {"notification_id": _dmx_notification_id(dmx_uid)},
        blocking=False,
    )


def _extract_json_error(data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract a non-empty error string from an OLA JSON payload."""
    if not isinstance(data, dict):
        return None

    error_value = data.get("error")
    if isinstance(error_value, str) and error_value.strip():
        return error_value.strip()

    message_value = data.get("message")
    if isinstance(message_value, str) and message_value.strip():
        return message_value.strip()

    errors_value = data.get("errors")
    if isinstance(errors_value, list):
        joined_errors = "; ".join(str(item).strip() for item in errors_value if str(item).strip())
        if joined_errors:
            return joined_errors

    return None


def _should_run_rdm_discovery(error_text: str) -> bool:
    """Return True when a lookup failure should trigger discovery and retry."""
    non_discovery_errors = (
        "Malformed request:",
        "Unexpected redirect HTTP",
        "Unexpected HTML response",
        "Invalid JSON response",
        "Missing IP address or OLA port",
    )
    return not error_text.startswith(non_discovery_errors)


def _get_cached_dmx_address(dmx_uid: str) -> Optional[int]:
    """Return a non-expired cached DMX address if one is available."""
    cache_entry = _dmx_address_cache.get(dmx_uid)
    if not cache_entry:
        return None

    if (datetime.now() - cache_entry["timestamp"]).total_seconds() >= DMX_ADDRESS_CACHE_SECONDS:
        _dmx_address_cache.pop(dmx_uid, None)
        return None

    try:
        return int(cache_entry["address"])
    except (TypeError, ValueError):
        _LOGGER.warning("Discarding invalid cached DMX address for %s: %s", dmx_uid, cache_entry)
        _dmx_address_cache.pop(dmx_uid, None)
        return None


def _cache_dmx_address(dmx_uid: str, address: int) -> None:
    """Store a DMX address in the in-memory cache."""
    _dmx_address_cache[dmx_uid] = {"address": address, "timestamp": datetime.now()}


def _create_background_task(
    hass: Optional[Any],
    coroutine: Any,
    name: str,
) -> asyncio.Task:
    """Create an asyncio task using Home Assistant when available."""
    if hass is not None and hasattr(hass, "async_create_background_task"):
        return hass.async_create_background_task(coroutine, name=name)
    return asyncio.create_task(coroutine, name=name)


async def _async_run_rdm_discovery_pipeline(
    hass: Optional[Any],
    ip_address: str,
    ola_port: int,
    universe: int,
) -> set[str]:
    """Run RDM discovery once, awaiting any in-flight discovery for the same universe."""
    key = (ip_address, ola_port, universe)
    existing_task = _pending_discovery_tasks.get(key)
    if existing_task and not existing_task.done():
        _LOGGER.debug(
            "Awaiting in-flight RDM discovery for universe %s at %s:%s",
            universe,
            ip_address,
            ola_port,
        )
        return await existing_task

    async def _runner() -> set[str]:
        discovery_url = f"http://{ip_address}:{ola_port}/rdm/run_discovery?id={universe}"
        _LOGGER.info(
            "Running RDM discovery for universe %s at %s:%s",
            universe,
            ip_address,
            ola_port,
        )

        async with aiohttp.ClientSession() as session:
            data, raw_text, error = await _async_fetch_json(
                session,
                discovery_url,
                timeout=RDM_DISCOVERY_TIMEOUT_SECONDS,
            )

        if error:
            raise RuntimeError(error)

        discovery_error = _extract_json_error(data)
        if discovery_error:
            raise RuntimeError(discovery_error)

        if not isinstance(data, dict):
            raise RuntimeError("Invalid discovery response")

        raw_uids = data.get("uids")
        if not isinstance(raw_uids, list) or not raw_uids:
            raise RuntimeError(
                f"RDM discovery returned no devices (response: {raw_text if raw_text is not None else '(no response)'})"
            )

        discovered_uids = {
            normalize_dmx_uid(str(entry.get("uid", "")))
            for entry in raw_uids
            if isinstance(entry, dict) and entry.get("uid")
        }
        discovered_uids.discard("")

        if not discovered_uids:
            raise RuntimeError("RDM discovery returned no valid UIDs")

        _LOGGER.info(
            "RDM discovery found %d device(s) for universe %s",
            len(discovered_uids),
            universe,
        )

        if hass is not None:
            async_dispatcher_send(
                hass,
                SIGNAL_DMX_DISCOVERY_COMPLETE,
                {
                    "uids": list(discovered_uids),
                    "ip_address": ip_address,
                    "ola_port": ola_port,
                    "universe": universe,
                },
            )

        return discovered_uids

    task = _create_background_task(
        hass,
        _runner(),
        name=f"savant_energy_rdm_discovery_{ip_address}_{universe}",
    )
    _pending_discovery_tasks[key] = task

    try:
        return await task
    finally:
        if _pending_discovery_tasks.get(key) is task:
            _pending_discovery_tasks.pop(key, None)


async def _async_fetch_dmx_address_once(
    ip_address: str,
    ola_port: int,
    universe: int,
    dmx_uid: str,
) -> Tuple[Optional[int], Optional[str]]:
    """Fetch a DMX address from uid_info once without fallback behavior."""
    url = f"http://{ip_address}:{ola_port}/json/rdm/uid_info?id={universe}&uid={dmx_uid}"

    async with aiohttp.ClientSession() as session:
        data, raw_text, fetch_error = await _async_fetch_json(
            session,
            url,
            timeout=UID_INFO_TIMEOUT_SECONDS,
        )

    if fetch_error:
        return None, fetch_error

    payload_error = _extract_json_error(data)
    if payload_error:
        if raw_text:
            _LOGGER.debug("RDM response for %s with error: %s", dmx_uid, raw_text)
        return None, payload_error

    if not isinstance(data, dict) or "address" not in data:
        if raw_text:
            _LOGGER.debug("RDM response for %s without address: %s", dmx_uid, raw_text)
        return None, "Address not present in response"

    try:
        address = int(data["address"])
    except (TypeError, ValueError):
        return None, f"Invalid address value: {data.get('address')}"

    if address <= 0:
        return None, f"Invalid address value: {address}"

    return address, None


def _get_fallback_dmx_address(
    hass: Optional[Any],
    dmx_uid: str,
    device_name: Optional[str],
) -> Tuple[Optional[int], Optional[str]]:
    """Return a fallback DMX address from cache or Home Assistant state."""
    cached_address = _get_cached_dmx_address(dmx_uid)
    if cached_address is not None:
        return cached_address, "cache"

    if hass is None:
        return None, None

    state_address = get_dmx_address_from_state(hass, dmx_uid, device_name)
    if state_address is not None:
        return state_address, "state"

    return None, None


def normalize_dmx_uid(uid: str) -> str:
    """Normalize a Savant UID or RDM UID into lowercase OLA uid_info format."""
    raw_uid = (uid or "").strip()
    if not raw_uid:
        return ""

    base_uid, _, suffix = raw_uid.partition(".")
    compact_uid = base_uid.replace(":", "").lower()
    if len(compact_uid) != 12:
        _LOGGER.warning("Unexpected UID format for DMX lookup: %s", uid)
        return base_uid.lower()

    try:
        manufacturer_id = compact_uid[:4]
        device_id = int(compact_uid[4:], 16)
    except ValueError:
        _LOGGER.warning("Invalid hexadecimal UID for DMX lookup: %s", uid)
        return base_uid.lower()

    if suffix == "1":
        device_id += 1
    elif suffix not in ("", "0"):
        _LOGGER.debug("Unexpected Savant UID suffix while formatting DMX UID: %s", uid)

    return f"{manufacturer_id}:{device_id:08x}"
def calculate_dmx_uid(uid: str) -> str:
    """
    Calculate the DMX UID based on the device UID, incrementing as hex if needed.
    Args:
        uid: Device UID string
    Returns:
        DMX UID string in the format XXXX:YYYYYY
    """
    return normalize_dmx_uid(uid)


def slugify(name: str) -> str:
    """
    Sanitize a string to be used in an entity_id: lowercase, underscores, no special chars, no double underscores.
    """
    import re
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    return name


def get_dmx_address_from_state(
    hass: Any,
    device_uid: str,
    device_name: Optional[str] = None,
) -> Optional[int]:
    """Resolve a DMX address from Home Assistant state using a stable device or DMX UID."""
    if not hass or not device_uid:
        return None

    lookup_uid = str(device_uid)
    normalized_lookup_uid = normalize_dmx_uid(lookup_uid)

    for sensor_state in hass.states.async_all("sensor"):
        if not sensor_state.entity_id.endswith("_dmx_address"):
            continue
        state_device_uid = str(sensor_state.attributes.get("uid", ""))
        state_dmx_uid = normalize_dmx_uid(str(sensor_state.attributes.get("dmx_uid", "")))
        if lookup_uid not in (state_device_uid, state_dmx_uid) and normalized_lookup_uid not in (
            normalize_dmx_uid(state_device_uid),
            state_dmx_uid,
        ):
            continue
        if sensor_state.state in ("unknown", "unavailable"):
            return None
        try:
            return int(sensor_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid DMX address in sensor %s: %s",
                sensor_state.entity_id,
                sensor_state.state,
            )
            return None

    legacy_entity_ids = [f"sensor.savant_energy_{lookup_uid}_dmx_address"]
    if device_name:
        legacy_entity_ids.insert(0, f"sensor.{slugify(device_name)}_dmx_address")

    for entity_id in legacy_entity_ids:
        state = hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            continue
        try:
            return int(state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid DMX address in sensor %s: %s",
                entity_id,
                state.state,
            )
            return None

    return None


async def async_get_dmx_address(
    ip_address: str,
    ola_port: int,
    universe: int,
    dmx_uid: str,
    hass: Optional[Any] = None,
    device_name: Optional[str] = None,
    schedule_discovery: bool = True,
) -> Optional[int]:
    """
    Get DMX address for a device using the RDM API.
    Args:
        ip_address: IP address of the OLA server
        ola_port: OLA server port
        universe: DMX universe ID (usually 1)
        dmx_uid: The DMX UID of the device
        hass: Optional Home Assistant instance for notifications
        device_name: Friendly device name for notifications
    Returns:
        The DMX address as an integer or None if not found
    """
    normalized_dmx_uid = normalize_dmx_uid(dmx_uid)
    if not normalized_dmx_uid:
        _LOGGER.warning("Missing or invalid DMX UID for address lookup: %s", dmx_uid)
        return None

    if not ip_address or not ola_port:
        last_error = "Missing IP address or OLA port for DMX address request"
        _LOGGER.warning(last_error)
    else:
        last_error = None

        address, error_text = await _async_fetch_dmx_address_once(
            ip_address,
            ola_port,
            universe,
            normalized_dmx_uid,
        )
        if address is not None:
            _cache_dmx_address(normalized_dmx_uid, address)
            _dmx_discovery_notifications.pop(normalized_dmx_uid, None)
            _dmx_last_lookup_error.pop(normalized_dmx_uid, None)
            await _async_clear_channel_issue(hass, normalized_dmx_uid)
            return address

        last_error = error_text or "Unknown error retrieving DMX address"
        _LOGGER.warning(
            "Initial uid_info lookup failed for %s on universe %s: %s",
            normalized_dmx_uid,
            universe,
            last_error,
        )

        if schedule_discovery and _should_run_rdm_discovery(last_error):
            try:
                discovered_uids = await _async_run_rdm_discovery_pipeline(
                    hass,
                    ip_address,
                    ola_port,
                    universe,
                )
                if normalized_dmx_uid not in discovered_uids:
                    _LOGGER.info(
                        "RDM discovery for universe %s did not report %s before retrying uid_info",
                        universe,
                        normalized_dmx_uid,
                    )

                address, retry_error = await _async_fetch_dmx_address_once(
                    ip_address,
                    ola_port,
                    universe,
                    normalized_dmx_uid,
                )
                if address is not None:
                    _cache_dmx_address(normalized_dmx_uid, address)
                    _dmx_discovery_notifications.pop(normalized_dmx_uid, None)
                    _dmx_last_lookup_error.pop(normalized_dmx_uid, None)
                    await _async_clear_channel_issue(hass, normalized_dmx_uid)
                    _LOGGER.info(
                        "Resolved DMX address for %s after RDM discovery",
                        normalized_dmx_uid,
                    )
                    return address

                last_error = retry_error or last_error
            except Exception as err:
                last_error = str(err)
                _LOGGER.warning(
                    "RDM discovery failed for %s on universe %s: %s",
                    normalized_dmx_uid,
                    universe,
                    last_error,
                )
        elif schedule_discovery:
            _LOGGER.warning(
                "Skipping RDM discovery for %s on universe %s because the uid_info response indicates a malformed or unexpected request/response: %s",
                normalized_dmx_uid,
                universe,
                last_error,
            )

    _dmx_last_lookup_error[normalized_dmx_uid] = last_error or "Unknown error retrieving DMX address"

    fallback_address, fallback_source = _get_fallback_dmx_address(
        hass,
        normalized_dmx_uid,
        device_name,
    )
    if fallback_address is not None and fallback_source is not None:
        _LOGGER.warning(
            "Using %s DMX address %s for %s after live lookup failed: %s",
            fallback_source,
            fallback_address,
            normalized_dmx_uid,
            _dmx_last_lookup_error[normalized_dmx_uid],
        )
        return fallback_address

    if hass is not None:
        previous_error = _dmx_discovery_notifications.get(normalized_dmx_uid)
        if previous_error != _dmx_last_lookup_error[normalized_dmx_uid]:
            _dmx_discovery_notifications[normalized_dmx_uid] = _dmx_last_lookup_error[normalized_dmx_uid]
            await _async_notify_channel_issue(
                hass,
                device_name or normalized_dmx_uid,
                normalized_dmx_uid,
                universe,
                _dmx_last_lookup_error[normalized_dmx_uid],
            )

    return None


async def async_build_managed_dmx_values(
    coordinator: Any,
    hass: Optional[Any],
    overrides_by_uid: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[int, str], Dict[str, int], Dict[str, str]]:
    """Build managed DMX channel values from snapshot state plus per-device overrides."""
    config_entry = getattr(coordinator, "config_entry", None)
    if config_entry is None:
        return {}, {}, {}

    snapshot_data = coordinator.data.get("snapshot_data", {}) if coordinator.data else {}
    devices = snapshot_data.get("presentDemands", []) if isinstance(snapshot_data, dict) else []
    if not isinstance(devices, list) or not devices:
        return {}, {}, {}

    ip_address = config_entry.data.get("address")
    ola_port = config_entry.data.get("ola_port", DEFAULT_OLA_PORT)
    if not ip_address or not ola_port:
        _LOGGER.warning("Missing IP address or OLA port while building managed DMX values")
        return {}, {}, {}

    normalized_overrides = {
        str(device_uid): _normalize_dmx_value(value, default="0")
        for device_uid, value in (overrides_by_uid or {}).items()
    }
    missing_override_uids = set(normalized_overrides)
    channel_values: Dict[int, str] = {}
    resolved_addresses: Dict[str, int] = {}
    unresolved_devices: Dict[str, str] = {}

    for device in devices:
        device_uid = str(device.get("uid") or "")
        if not device_uid:
            continue

        device_name = str(device.get("name") or device_uid)
        missing_override_uids.discard(device_uid)
        desired_value = normalized_overrides.get(device_uid)
        if desired_value is None:
            percent_commanded = device.get("percentCommanded")
            if percent_commanded is None:
                continue
            try:
                desired_value = "255" if float(percent_commanded) > 0 else "0"
            except (TypeError, ValueError):
                _LOGGER.debug(
                    "Skipping %s because percentCommanded is invalid: %s",
                    device_name,
                    percent_commanded,
                )
                continue

        dmx_address = await async_get_dmx_address(
            ip_address,
            ola_port,
            1,
            calculate_dmx_uid(device_uid),
            hass=hass,
            device_name=device_name,
        )
        if dmx_address is None:
            unresolved_devices[device_uid] = device_name
            continue

        resolved_addresses[device_uid] = dmx_address
        channel_values[dmx_address] = desired_value

    for missing_uid in missing_override_uids:
        unresolved_devices.setdefault(missing_uid, missing_uid)

    return channel_values, resolved_addresses, unresolved_devices


async def async_get_dmx_status_batch(
    ip_address: str,
    channels: list,
    ola_port: int = DEFAULT_OLA_PORT,
) -> dict:
    """
    Get DMX status for specified channels in one batch.
    Args:
        ip_address: IP address of the OLA server
        channels: List of DMX channels to check
        ola_port: OLA server port
    Returns:
        Dictionary mapping channel numbers to boolean status (True = on, False = off)
    """
    global _last_successful_api_call, _api_failure_count, _api_request_count
    
    if not channels or len(channels) == 0:
        _LOGGER.warning("Channels parameter is required but was empty - nothing to check")
        return {}
    
    int_channels: list[int] = []
    for ch in channels:
        try:
            int_channels.append(int(ch))
        except (ValueError, TypeError):
            _LOGGER.debug(f"Skipping invalid channel value in batch request: {ch}")

    if not ip_address or not ola_port:
        _LOGGER.debug("Missing IP address or OLA port for DMX request")
        return {}
    
    url = f"http://{ip_address}:{ola_port}/get_dmx?u=1"
    
    dmx_status_dict = {}
    
    try:
        _api_request_count += 1
        
        async with aiohttp.ClientSession() as session:
            timeout_config = aiohttp.ClientTimeout(total=10.0)
            async with session.get(url, timeout=timeout_config) as response:
                if response.status == 200:
                    data = await response.text()
                    try:
                        json_data = json.loads(data)
                        if "dmx" not in json_data:
                            _LOGGER.error("Batch DMX response missing 'dmx' key")
                            _api_failure_count += 1
                        else:
                            dmx_values = json_data["dmx"]
                            max_index = len(dmx_values)
                            for channel in int_channels:
                                idx = channel - 1
                                if 0 <= idx < max_index:
                                    value = dmx_values[idx]
                                    dmx_status_dict[channel] = value != DMX_OFF_VALUE
                                else:
                                    _LOGGER.debug(
                                        f"Channel {channel} out of range for batch (max {max_index})"
                                    )
                            _last_successful_api_call = datetime.now()
                            
                    except json.JSONDecodeError as e:
                        _LOGGER.error(f"Error parsing JSON response: {e}, data: '{data}'")
                        _api_failure_count += 1
                else:
                    _LOGGER.debug(f"DMX request failed with status {response.status}, response: {await response.text()}")
                    _api_failure_count += 1
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.debug(f"Network error making DMX request: {type(err).__name__}: {err}")
        _api_failure_count += 1
    except Exception as err:
        _LOGGER.debug(f"Unexpected error in DMX request: {type(err).__name__}: {err}")
        _api_failure_count += 1
    
    return dmx_status_dict


async def async_get_all_dmx_status(
    ip_address: str,
    channels: list,
    ola_port: int = DEFAULT_OLA_PORT,
) -> dict:
    """
    Convenience wrapper that returns DMX on/off status for a list of channels.
    Uses the batch API to fetch the full DMX universe once and maps the requested channels.
    """
    return await async_get_dmx_status_batch(ip_address, channels, ola_port)


async def async_get_dmx_status(ip_address: str, channel: int, ola_port: int = DEFAULT_OLA_PORT) -> Optional[bool]:
    """
    Get DMX status for a specific channel.
    Args:
        ip_address: IP address of the OLA server
        channel: DMX channel number
        ola_port: OLA server port
    Returns:
        Boolean status (True = on, False = off) or None if unavailable
    """
    global _last_successful_api_call, _api_failure_count, _api_request_count
    
    _LOGGER.debug(f"DMX STATUS REQUEST - Channel: {channel}, IP: {ip_address}, Port: {ola_port}")
    
    if not ip_address or not ola_port:
        _LOGGER.debug("Missing IP address or OLA port for DMX request")
        return None
    
    url = f"http://{ip_address}:{ola_port}/get_dmx?u=1"
    
    try:
        _api_request_count += 1
        async with aiohttp.ClientSession() as session:
            timeout_config = aiohttp.ClientTimeout(total=10.0)
            async with session.get(url, timeout=timeout_config) as response:
                _LOGGER.debug(f"Got response with status: {response.status}")
                if response.status == 200:
                    data = await response.text()
                    try:
                        json_data = json.loads(data)
                        if "dmx" in json_data:
                            dmx_values = json_data["dmx"]
                            
                            if 0 <= channel-1 < len(dmx_values):
                                value = dmx_values[channel-1]
                                dmx_status = value != DMX_OFF_VALUE
                                _last_successful_api_call = datetime.now()
                                return dmx_status
                            else:
                                _LOGGER.warning(f"Channel {channel} is out of range (max: {len(dmx_values)})")
                        else:
                            _LOGGER.error(f"Expected 'dmx' key not found in JSON response: {json_data}")
                    except json.JSONDecodeError as e:
                        _LOGGER.debug(f"Invalid JSON response format: '{data}' - Error: {e}")
                        _api_failure_count += 1
                else:
                    _LOGGER.debug(f"DMX request failed with status {response.status}, response: {await response.text()}")
                    _api_failure_count += 1
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.debug(f"Network error making DMX request: {type(err).__name__}: {err}")
        _api_failure_count += 1
    except Exception as err:
        _LOGGER.debug(f"Unexpected error in DMX request: {type(err).__name__}: {err}")
        _api_failure_count += 1
    
    return None


async def _execute_curl_command(cmd: str) -> tuple[int, str, str]:
    """
    Execute the given curl command asynchronously.
    Args:
        cmd: Curl command string
    Returns:
        Tuple containing (returncode, stdout, stderr)
    """
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    returncode = process.returncode if process.returncode is not None else -1
    return returncode, stdout.decode(), stderr.decode()


def _normalize_dmx_value(value: Any, default: str = "255") -> str:
    """Normalize a DMX value to a stringified integer between 0 and 255."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "on":
            return "255"
        if normalized == "off":
            return "0"
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return default
    return str(max(0, min(255, numeric_value)))


async def _async_get_current_dmx_values(
    ip_address: str,
    ola_port: int,
    max_channel: int,
) -> list[str]:
    """Fetch the current DMX universe and return normalized values up to max_channel."""
    if not ip_address or not ola_port or max_channel <= 0:
        return []

    url = f"http://{ip_address}:{ola_port}/get_dmx?u=1"

    try:
        async with aiohttp.ClientSession() as session:
            timeout_config = aiohttp.ClientTimeout(total=10.0)
            async with session.get(url, timeout=timeout_config) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "Unable to fetch current DMX values before set; status=%s response=%s",
                        response.status,
                        await response.text(),
                    )
                    return []

                payload = json.loads(await response.text())
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as err:
        _LOGGER.debug("Unable to fetch current DMX values before set: %s", err)
        return []
    except Exception as err:
        _LOGGER.debug("Unexpected error fetching current DMX values before set: %s", err)
        return []

    dmx_values = payload.get("dmx")
    if not isinstance(dmx_values, list):
        _LOGGER.debug("Current DMX payload did not include a valid dmx list: %s", payload)
        return []

    return [_normalize_dmx_value(value) for value in dmx_values[:max_channel]]


async def async_set_dmx_values(ip_address: str, channel_values: Dict[int, str], ola_port: int = 9090, testing_mode: bool = False) -> Dict[str, Any]:
    """
    Set DMX values for channels.
    Args:
        ip_address: IP address of the OLA server
        channel_values: Dictionary mapping channel numbers (starting at 1) to values
        ola_port: Port for the OLA server
        testing_mode: If True, only log the command without executing it
    Returns:
        True if successful, False otherwise
    """
    global _dmx_api_stats
    _dmx_api_stats["request_count"] += 1
    
    try:
        max_channel = max(channel_values.keys()) if channel_values else 0
        if max_channel == 0:
            _LOGGER.warning("No DMX channel values were provided")
            return {"success": False, "status": None, "text": None, "json": None, "error": "No channel values provided"}

        value_array = ["0"] * max_channel

        if not testing_mode:
            current_values = await _async_get_current_dmx_values(
                ip_address,
                ola_port,
                max_channel,
            )
            for index, current_value in enumerate(current_values):
                value_array[index] = current_value
        
        for channel, value in channel_values.items():
            if 1 <= channel <= max_channel:
                value_array[channel - 1] = _normalize_dmx_value(value, default="0")

        data_param = ",".join(value_array)

        url = f"http://{ip_address}:{ola_port}/set_dmx"
        log_level = logging.INFO if testing_mode else logging.DEBUG
        _LOGGER.log(log_level, f"DMX COMMAND {'(TESTING MODE - NOT SENT)' if testing_mode else '(sending)'}: POST {url} u=1 d={data_param}")

        if testing_mode:
            _dmx_api_stats["last_successful_call"] = datetime.now()
            _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) /
                                              _dmx_api_stats["request_count"]) * 100.0
            return {"success": True, "status": None, "text": "(testing)", "json": None}

        # Perform aiohttp POST to OLA
        try:
            timeout_cfg = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                async with session.post(url, data={"u": "1", "d": data_param}) as resp:
                    status = resp.status
                    text = await resp.text()
                    json_body = None
                    if _LOGGER.isEnabledFor(logging.DEBUG):
                        _LOGGER.debug(f"DMX POST response status: {status}, body: {text}")
                    try:
                        json_body = json.loads(text)
                    except Exception:
                        json_body = None

                    if status != 200:
                        _LOGGER.error(f"DMX POST failed with status {status}: {text}")
                        _dmx_api_stats["failure_count"] += 1
                        _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) /
                                                          _dmx_api_stats["request_count"]) * 100.0
                        return {"success": False, "status": status, "text": text, "json": json_body}

                    # Successful HTTP 200
                    _LOGGER.info(f"DMX command response: {text}")
                    _dmx_api_stats["last_successful_call"] = datetime.now()
                    _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) /
                                                      _dmx_api_stats["request_count"]) * 100.0
                    return {"success": True, "status": status, "text": text, "json": json_body}

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error(f"Network error setting DMX values: {type(err).__name__}: {err}")
            _dmx_api_stats["failure_count"] += 1
            _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) /
                                              _dmx_api_stats["request_count"]) * 100.0
            return {"success": False, "status": None, "text": None, "json": None, "error": str(err)}
        
    except Exception as e:
        _LOGGER.error(f"Failed to set DMX values: {str(e)}")
        _dmx_api_stats["failure_count"] += 1
        _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) / 
                                        _dmx_api_stats["request_count"]) * 100.0
        return {"success": False, "status": None, "text": None, "json": None, "error": str(e)}


def is_dmx_api_available() -> bool:
    """
    Check if the DMX API is currently available.
    Returns:
        True if the API is available, False otherwise
    """
    global _last_successful_api_call
    
    if _last_successful_api_call is None:
        return True
        
    time_since_last_success = datetime.now() - _last_successful_api_call
    return time_since_last_success.total_seconds() < DMX_API_TIMEOUT


def get_dmx_api_stats() -> Dict[str, Any]:
    """
    Return current DMX API statistics.
    Returns:
        Dictionary containing API statistics
    """
    return _dmx_api_stats