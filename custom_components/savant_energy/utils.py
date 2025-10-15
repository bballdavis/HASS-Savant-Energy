"""Utility functions for Savant Energy integration.
Provides DMX, API, and helper routines for the integration.
All utility functions are now documented for clarity and open source maintainability.
"""

import logging
import asyncio
import subprocess
import json
from datetime import datetime, timedelta
import aiohttp
from typing import List, Dict, Any, Optional, Final, Tuple, Union

from .const import DEFAULT_OLA_PORT

_LOGGER = logging.getLogger(__name__)

# DMX API constants
DMX_ON_VALUE: Final = 255
DMX_OFF_VALUE: Final = 0
DMX_CACHE_SECONDS: Final = 5  # Cache DMX status for 5 seconds
DMX_API_TIMEOUT: Final = 30  # Time in seconds to consider API down
DMX_ADDRESS_CACHE_SECONDS: Final = 3600  # Cache DMX address for 1 hour
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


async def _async_fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Fetch JSON data and return payload, raw text, and error string."""
    try:
        timeout_config = aiohttp.ClientTimeout(total=float(timeout))
        async with session.get(url, timeout=timeout_config) as response:
            text_response = await response.text()
            if response.status != 200:
                error = f"HTTP {response.status}"
                _LOGGER.warning(
                    f"Request to {url} failed with {error}, response: {text_response}"
                )
                return None, text_response, error
            try:
                data = json.loads(text_response)
            except json.JSONDecodeError as json_err:
                error = f"Invalid JSON: {json_err}"
                _LOGGER.warning(
                    f"JSON decode error from {url}: {error}. Text: {text_response}"
                )
                return None, text_response, error
            return data, text_response, None
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        error = f"{type(err).__name__}: {err}"
        _LOGGER.warning(f"Network error calling {url}: {error}")
        return None, None, error
    except Exception as err:
        error = f"Unexpected {type(err).__name__}: {err}"
        _LOGGER.warning(f"Unexpected error calling {url}: {error}")
        return None, None, error


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
    from .const import DOMAIN  # Local import to avoid circular dependency at import time

    slug = slugify(device_label)
    notification_id = f"{DOMAIN}_dmx_{slug}"
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


def calculate_dmx_uid(uid: str) -> str:
    """
    Calculate the DMX UID based on the device UID, incrementing as hex if needed.
    Args:
        uid: Device UID string
    Returns:
        DMX UID string in the format XXXX:YYYYYY
    """
    base_uid = uid.split(".")[0]
    base_uid = f"{base_uid[:4]}:{base_uid[4:]}"
    if uid.endswith(".1"):
        prefix = base_uid[:-2]
        last_two = base_uid[-2:]
        try:
            incremented = f"{int(last_two, 16) + 1:02X}"
        except Exception:
            incremented = last_two
        base_uid = prefix + incremented
    return base_uid


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


async def async_get_dmx_address(
    ip_address: str,
    ola_port: int,
    universe: int,
    dmx_uid: str,
    hass: Optional[Any] = None,
    device_name: Optional[str] = None,
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
    global _dmx_address_cache

    cache_key = dmx_uid
    now = datetime.now()

    if cache_key in _dmx_address_cache:
        cache_entry = _dmx_address_cache[cache_key]
        if (now - cache_entry["timestamp"]).total_seconds() < DMX_ADDRESS_CACHE_SECONDS:
            _LOGGER.debug(
                f"Using cached DMX address {cache_entry['address']} for device {dmx_uid}"
            )
            return cache_entry["address"]

    if not ip_address or not ola_port:
        _LOGGER.warning("Missing IP address or OLA port for DMX address request")
        return None

    url = f"http://{ip_address}:{ola_port}/json/rdm/uid_info?id={universe}&uid={dmx_uid}"
    discovery_triggered = False
    last_error: Optional[str] = None

    try:
        async with aiohttp.ClientSession() as session:
            for attempt in range(2):
                data, raw_text, fetch_error = await _async_fetch_json(
                    session, url, timeout=10
                )

                if data and "address" in data:
                    try:
                        address = int(data["address"])
                    except (TypeError, ValueError):
                        last_error = f"Invalid address value: {data.get('address')}"
                        _LOGGER.warning(
                            f"Invalid address in RDM response for {dmx_uid}: {data}"
                        )
                    else:
                        _dmx_address_cache[cache_key] = {
                            "address": address,
                            "timestamp": now,
                        }
                        if discovery_triggered:
                            _dmx_discovery_notifications.pop(dmx_uid, None)
                        return address

                error_text: Optional[str] = fetch_error
                if data and "address" not in data:
                    error_text = str(
                        data.get("error")
                        or data.get("message")
                        or (
                            "; ".join(str(item) for item in data.get("errors", []))
                            if isinstance(data.get("errors"), list)
                            else None
                        )
                        or "Address not present in response"
                    )
                    if raw_text:
                        _LOGGER.debug(
                            f"RDM response for {dmx_uid} without address: {raw_text}"
                        )

                if error_text == RDM_DEVICE_NOT_FOUND and attempt == 0:
                    discovery_triggered = True
                    discovery_url = (
                        f"http://{ip_address}:{ola_port}/rdm/run_discovery?id={universe}&incremental=true"
                    )
                    _LOGGER.info(
                        "RDM device %s not found; triggering discovery on universe %s",
                        dmx_uid,
                        universe,
                    )
                    discovery_data, _, discovery_error = await _async_fetch_json(
                        session, discovery_url, timeout=30
                    )
                    if discovery_error:
                        last_error = discovery_error
                        _LOGGER.warning(
                            "RDM discovery failed for %s on universe %s: %s",
                            dmx_uid,
                            universe,
                            discovery_error,
                        )
                        break
                    if discovery_data and isinstance(discovery_data, dict):
                        discovered_count = len(discovery_data.get("uids", []))
                        _LOGGER.debug(
                            "RDM discovery returned %d uid(s) for universe %s",
                            discovered_count,
                            universe,
                        )
                    continue

                if error_text:
                    last_error = error_text
                else:
                    last_error = "Unknown error retrieving DMX address"
                break
    except Exception as err:
        last_error = f"Unexpected {type(err).__name__}: {err}"
        _LOGGER.warning(f"Unexpected error fetching DMX address for {dmx_uid}: {last_error}")

    if discovery_triggered and last_error:
        previous_error = _dmx_discovery_notifications.get(dmx_uid)
        if previous_error != last_error:
            _dmx_discovery_notifications[dmx_uid] = last_error
            label = device_name or dmx_uid
            await _async_notify_channel_issue(hass, label, dmx_uid, universe, last_error)

    return None


async def async_get_all_dmx_status(ip_address: str, channels: List[int], ola_port: int = DEFAULT_OLA_PORT) -> Dict[int, bool]:
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
    
    int_channels = []
    for ch in channels:
        try:
            int_channels.append(int(ch))
        except (ValueError, TypeError):
            _LOGGER.warning(f"Skipping invalid channel: {ch}")

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
                        if "dmx" in json_data:
                            dmx_values = json_data["dmx"]
                            
                            for channel in int_channels:
                                if 0 <= channel-1 < len(dmx_values):
                                    channel_value = dmx_values[channel-1]
                                    dmx_status = channel_value != DMX_OFF_VALUE
                                    dmx_status_dict[channel] = dmx_status
                                else:
                                    _LOGGER.warning(f"Channel {channel} is out of range (max: {len(dmx_values)})")
                            
                            _last_successful_api_call = datetime.now()
                        else:
                            _LOGGER.error(f"Expected 'dmx' key not found in JSON response: {json_data}")
                            _api_failure_count += 1
                            
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


async def async_set_dmx_values(ip_address: str, channel_values: Dict[int, str], ola_port: int = 9090, testing_mode: bool = False) -> bool:
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
        
        value_array = ["0"] * max_channel
        
        for channel, value in channel_values.items():
            if 1 <= channel <= max_channel:
                if str(value) == "255" or str(value).lower() == "on" or str(value) == "1":
                    value_array[channel-1] = "255"
                else:
                    value_array[channel-1] = "0"
        
        data_param = ",".join(value_array)
        
        cmd = f'curl -X POST -d "u=1&d={data_param}" http://{ip_address}:{ola_port}/set_dmx'
        
        log_level = logging.INFO if testing_mode else logging.DEBUG
        _LOGGER.log(log_level, f"DMX COMMAND {'(TESTING MODE - NOT SENT)' if testing_mode else '(sending)'}: {cmd}")
        
        if testing_mode:
            _dmx_api_stats["last_successful_call"] = datetime.now()
            _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) / 
                                            _dmx_api_stats["request_count"]) * 100.0
            return True
        
        returncode, stdout, stderr = await _execute_curl_command(cmd)
        if returncode != 0:
            _LOGGER.error(f"Error setting DMX values: {stderr}")
            _dmx_api_stats["failure_count"] += 1
            _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) / 
                                            _dmx_api_stats["request_count"]) * 100.0
            return False
        _LOGGER.info(f"DMX command response: {stdout}")

        _dmx_api_stats["last_successful_call"] = datetime.now()
        _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) / 
                                        _dmx_api_stats["request_count"]) * 100.0
        return True
        
    except Exception as e:
        _LOGGER.error(f"Failed to set DMX values: {str(e)}")
        _dmx_api_stats["failure_count"] += 1
        _dmx_api_stats["success_rate"] = ((_dmx_api_stats["request_count"] - _dmx_api_stats["failure_count"]) / 
                                        _dmx_api_stats["request_count"]) * 100.0
        return False


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