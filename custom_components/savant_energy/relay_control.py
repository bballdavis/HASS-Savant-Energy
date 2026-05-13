"""Direct SEM port 2000 relay control for Savant Energy."""

import asyncio
import base64
import json
import logging
import socket
import uuid
from typing import Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)


class SavantRelayController:
    """Direct TCP socket client for controlling Savant relays via SEM port 2000."""

    def __init__(self, sem_host: str = "192.168.1.108", sem_port: int = 2000):
        """
        Initialize relay controller.

        Args:
            sem_host: SEM IP address (default 192.168.1.108)
            sem_port: SEM command port (default 2000)
        """
        self.sem_host = sem_host
        self.sem_port = sem_port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._relay_uid_map: dict[str, str] = {}  # Maps circuit UUID -> relay UID
        
        # Legacy device UID - typically set from companion/status API
        # For smoke detector example: "001AAE1733DB"
        self.default_relay_uid: str = ""

    async def connect(self) -> bool:
        """Connect to SEM port 2000."""
        if self._connected:
            return True

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.sem_host, self.sem_port),
                timeout=10.0,
            )
            self._connected = True
            _LOGGER.info("Connected to SEM at %s:%d", self.sem_host, self.sem_port)
            return True
        except Exception as exc:
            _LOGGER.error("Failed to connect to SEM: %s", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from SEM."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        self._reader = None
        self._writer = None

    async def set_relay_uid_map(self, uuid_to_uid: dict[str, str]) -> None:
        """Store mapping of circuit UUIDs to relay UIDs."""
        self._relay_uid_map = uuid_to_uid.copy()

    def _get_relay_uid(self, circuit_uid: Optional[str] = None) -> str:
        """Get the legacy relay UID for a circuit."""
        if not circuit_uid:
            return self.default_relay_uid
        
        # Check if circuit_uid is already a legacy UID format (simple heuristic)
        if len(circuit_uid) == 12 and all(c in '0123456789ABCDEF' for c in circuit_uid.upper()):
            return circuit_uid
        
        # Otherwise try to look it up in the map
        return self._relay_uid_map.get(circuit_uid, self.default_relay_uid)

    async def _send_set_load_state(self, states: dict[str, int]) -> bool:
        """Send one SET_LOAD_STATE frame with an arbitrary states dict and return success."""
        if not self._connected:
            if not await self.connect():
                return False

        if not self._writer or not self._reader:
            _LOGGER.error("Writer/reader not available")
            return False

        payload = {"states": states, "requestId": str(uuid.uuid4())}
        b64_payload = base64.b64encode(json.dumps(payload).encode()).decode()
        command = f"SET_LOAD_STATE={b64_payload}\n"

        try:
            self._writer.write(command.encode())
            await asyncio.wait_for(self._writer.drain(), timeout=5.0)
            _LOGGER.debug("Sent SET_LOAD_STATE for %d relay(s)", len(states))
        except Exception as exc:
            _LOGGER.error("Failed to send SET_LOAD_STATE: %s", exc)
            self._connected = False
            return False

        try:
            response_data = await asyncio.wait_for(
                self._reader.readuntil(b"\n"),
                timeout=2.0,
            )
            response_str = response_data.decode("utf-8", errors="ignore").strip()
            if response_str.startswith("SET_LOAD_STATE_RESPONSE="):
                b64_response = response_str[len("SET_LOAD_STATE_RESPONSE="):]
                try:
                    response_json = json.loads(base64.b64decode(b64_response))
                    if response_json.get("status") == "OK":
                        _LOGGER.info("SET_LOAD_STATE OK for %d relay(s)", len(states))
                        return True
                    _LOGGER.warning("SET_LOAD_STATE failed: %s", response_json)
                    return False
                except Exception as exc:
                    _LOGGER.warning("Failed to decode SET_LOAD_STATE response: %s", exc)
        except asyncio.TimeoutError:
            # SEM doesn't always respond; the command is still applied.
            _LOGGER.debug("No SET_LOAD_STATE response (timeout) — command was sent")
            return True
        except Exception as exc:
            _LOGGER.error("Error reading SET_LOAD_STATE response: %s", exc)
            self._connected = False
            return False

        return True

    async def set_relay_state(self, relay_uid: str, state: int) -> bool:
        """Send SET_LOAD_STATE for a single relay.

        Args:
            relay_uid: Legacy relay UID (e.g., "001AAE1733DB")
            state: 0 for OFF, 100 for ON
        """
        return await self._send_set_load_state({relay_uid: state})

    async def set_relay_states_bulk(self, states: dict[str, int]) -> bool:
        """Send SET_LOAD_STATE for multiple relays in a single command.

        Args:
            states: Mapping of relay_uid → state (0=OFF, 100=ON)
        """
        if not states:
            return True
        _LOGGER.info("Sending bulk SET_LOAD_STATE for %d relay(s)", len(states))
        return await self._send_set_load_state(states)

    async def turn_on(self, relay_uid: Optional[str] = None) -> bool:
        """Turn on a relay (state=100)."""
        uid = relay_uid or self.default_relay_uid
        if not uid:
            _LOGGER.error("No relay UID specified")
            return False
        return await self.set_relay_state(uid, 100)

    async def turn_off(self, relay_uid: Optional[str] = None) -> bool:
        """Turn off a relay (state=0)."""
        uid = relay_uid or self.default_relay_uid
        if not uid:
            _LOGGER.error("No relay UID specified")
            return False
        return await self.set_relay_state(uid, 0)

    async def fetch_relay_uids_from_sem(self) -> dict[str, str]:
        """
        Fetch relay device list from SEM companion API.
        
        Returns:
            Dict mapping device names to legacy UIDs
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{self.sem_host}:8644/companion/status"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        devices = {}
                        
                        # Extract relay devices from the status (note: "Devices" is capitalized)
                        for device in data.get("Devices", []):
                            uid = device.get("UID")
                            name = device.get("LoadName", "")
                            if uid and name:
                                devices[name.lower()] = uid
                        
                        _LOGGER.info("Fetched %d relay devices from SEM", len(devices))
                        return devices
        except Exception as exc:
            _LOGGER.error("Failed to fetch relay UIDs from SEM: %s", exc)
        
        return {}
