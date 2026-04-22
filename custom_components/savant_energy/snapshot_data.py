# custom_components/energy_snapshot/snapshot_data.py
"""
Handles fetching and decoding the current energy snapshot from the Savant controller.
All functions are now documented for clarity and open source maintainability.
"""

import socket
import base64
import json
import logging

_LOGGER = logging.getLogger(__name__)


def get_current_energy_snapshot(address, port):
    """
    Retrieves the current energy snapshot from the Savant controller.
    Connects via TCP, decodes the base64 payload, and parses the JSON.
    Args:
        address: IP address of the Savant controller
        port: Port for the energy snapshot service
    Returns:
        Parsed JSON data as a dict, or None on error.
    """
    _LOGGER.info(f"get_current_energy_snapshot called with address={address}, port={port}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((address, port))
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if data.count(b"\n") >= 2:
                    break
        if not data:
            return None
        data_str = data.decode("utf-8")
        # Extract the value of SET_ENERGY
        if "SET_ENERGY=" in data_str:
            data_str = data_str.split("SET_ENERGY=", 1)[1]
        # Strip off everything after the newline that follows SET_ENERGY
        if "\n" in data_str:
            data_str = data_str.split("\n", 1)[0]
        _LOGGER.debug(f"Data after decode length: {len(data_str)})")
        if "\n" in data_str:
            data_str = data_str.split("\n", 1)[1]
        if data_str.startswith("SET_ENERGY="):
            data_str = data_str[len("SET_ENERGY=") :]
        _LOGGER.debug(
            f"Processed data string: {data_str[:100]}... (length: {len(data_str)})"
        )
        try:
            decoded_string = base64.b64decode(data_str).decode("utf-8")
            _LOGGER.debug(
                f"Decoded string: {decoded_string[:100]}... (length: {len(decoded_string)})"
            )
        except base64.binascii.Error as e:
            _LOGGER.error(f"Decode Error: {e}, Data Length: {len(data_str)}")
            return None
        try:
            json_data = json.loads(decoded_string)
            present_demands = json_data.get("presentDemands")
            if isinstance(present_demands, list):
                _LOGGER.info(
                    "Decoded Savant snapshot with %d presentDemands entries",
                    len(present_demands),
                )
                for index, device in enumerate(present_demands):
                    if not isinstance(device, dict):
                        _LOGGER.warning(
                            "presentDemands[%d] is not an object: %r",
                            index,
                            device,
                        )
                        continue
                    _LOGGER.debug(
                        "Snapshot device[%d]: uid=%s name=%s channel=%s percentCommanded=%s power=%s voltage=%s capacity=%s classification=%s",
                        index,
                        device.get("uid"),
                        device.get("name"),
                        device.get("channel"),
                        device.get("percentCommanded"),
                        device.get("power"),
                        device.get("voltage"),
                        device.get("capacity"),
                        device.get("classification"),
                    )
            else:
                _LOGGER.warning(
                    "Decoded Savant snapshot is missing a list presentDemands payload: %s",
                    type(present_demands).__name__,
                )
            _LOGGER.info(f"get_current_energy_snapshot returning data with {len(json_data.get('presentDemands', []))} devices")
            return json_data
        except json.JSONDecodeError as e:
            _LOGGER.error(f"JSON Error: {e}, JSON: {decoded_string}")
            return None
    except socket.error as e:
        _LOGGER.error(f"Socket Error fetching snapshot: {e}")
        return None
    except Exception as e:
        _LOGGER.error(f"Unexpected Error: {e}")
        return None
