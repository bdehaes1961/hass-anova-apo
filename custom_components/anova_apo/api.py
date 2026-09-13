"""Websocket client for the Anova Precision Oven cloud API."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import ELEMENT_PRESETS, PLATFORM_ID, WS_SUBPROTOCOL, WS_URL

_LOGGER = logging.getLogger(__name__)

RECONNECT_MIN = 5
RECONNECT_MAX = 300
COMMAND_TIMEOUT = 15


class AnovaError(Exception):
    """Generic Anova error."""


class InvalidAuth(AnovaError):
    """Token rejected by the cloud."""


class NoDevicesFound(AnovaError):
    """No ovens paired to this account."""


class CommandError(AnovaError):
    """The oven rejected a command."""


def _f(celsius: float) -> float:
    return round(celsius * 9 / 5 + 32, 2)


def build_stages(
    *,
    temperature: float,
    bulb_mode: str = "dry",
    steam_mode: str = "off",
    steam_percentage: int | None = None,
    relative_humidity: int | None = None,
    fan_speed: int = 100,
    heating_elements: str | dict[str, bool] = "rear",
    vent_open: bool = False,
    rack_position: int = 3,
    timer_seconds: int | None = None,
    probe_target: float | None = None,
) -> list[dict[str, Any]]:
    """Build a preheat + cook stage pair for an oven_v1 cook."""
    if isinstance(heating_elements, str):
        elements = ELEMENT_PRESETS.get(heating_elements, ELEMENT_PRESETS["rear"])
    else:
        elements = heating_elements

    setpoint = {"celsius": round(float(temperature), 2), "fahrenheit": _f(temperature)}
    common: dict[str, Any] = {
        "stepType": "stage",
        "description": "",
        "userActionRequired": False,
        "temperatureBulbs": {bulb_mode: {"setpoint": setpoint}, "mode": bulb_mode},
        "heatingElements": {
            "top": {"on": bool(elements.get("top"))},
            "bottom": {"on": bool(elements.get("bottom"))},
            "rear": {"on": bool(elements.get("rear"))},
        },
        "fan": {"speed": int(fan_speed)},
        "vent": {"open": bool(vent_open)},
        "rackPosition": int(rack_position),
    }

    if steam_mode == "steam-percentage":
        common["steamGenerators"] = {
            "mode": "steam-percentage",
            "steamPercentage": {"setpoint": int(steam_percentage or 0)},
        }
    elif steam_mode == "relative-humidity":
        common["steamGenerators"] = {
            "mode": "relative-humidity",
            "relativeHumidity": {"setpoint": int(relative_humidity or 0)},
        }

    preheat = dict(common)
    preheat.update(
        {"id": f"{PLATFORM_ID}-{uuid.uuid4()}", "title": "Home Assistant", "type": "preheat"}
    )

    cook = dict(common)
    cook.update({"id": f"{PLATFORM_ID}-{uuid.uuid4()}", "title": "", "type": "cook"})

    # Timer and probe are mutually exclusive in the Anova API.
    if probe_target is not None:
        cook["probeAdded"] = True
        cook["timerAdded"] = False
        cook["temperatureProbe"] = {
            "setpoint": {
                "celsius": round(float(probe_target), 2),
                "fahrenheit": _f(probe_target),
            }
        }
    elif timer_seconds:
        cook["timerAdded"] = True
        cook["probeAdded"] = False
        cook["timer"] = {"initial": int(timer_seconds)}
    else:
        cook["timerAdded"] = False
        cook["probeAdded"] = False

    return [preheat, cook]


class AnovaApoApi:
    """Maintains a single websocket connection to the Anova cloud."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        on_state: Callable[[str, dict[str, Any]], None] | None = None,
        on_devices: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._token = access_token
        self._on_state = on_state
        self._on_devices = on_devices
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._futures: dict[str, asyncio.Future] = {}
        self.devices: dict[str, dict[str, Any]] = {}
        self.states: dict[str, dict[str, Any]] = {}
        self.connected = asyncio.Event()
        self._devices_seen = asyncio.Event()

    @property
    def url(self) -> str:
        """Return the websocket URL including the token."""
        return (
            f"{WS_URL}?token={self._token}"
            f"&supportedAccessories=APO&platform={PLATFORM_ID}"
        )

    async def start(self) -> None:
        """Start the background connection loop."""
        self._stopping = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the connection loop."""
        self._stopping = True
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def async_validate(self) -> list[dict[str, Any]]:
        """Connect once and return the paired ovens (used by the config flow)."""
        try:
            async with self._session.ws_connect(
                self.url, protocols=(WS_SUBPROTOCOL,), heartbeat=30, timeout=30
            ) as ws:
                deadline = asyncio.get_running_loop().time() + 25
                while asyncio.get_running_loop().time() < deadline:
                    msg = await ws.receive(timeout=15)
                    if msg.type is not aiohttp.WSMsgType.TEXT:
                        raise InvalidAuth("Connection closed by server")
                    data = json.loads(msg.data)
                    if data.get("command") == "EVENT_APO_WIFI_LIST":
                        devices = data.get("payload") or []
                        if not devices:
                            raise NoDevicesFound
                        return devices
        except aiohttp.WSServerHandshakeError as err:
            raise InvalidAuth(str(err)) from err
        except (TimeoutError, asyncio.TimeoutError) as err:
            raise InvalidAuth("Timeout waiting for oven list") from err
        raise NoDevicesFound

    async def _run(self) -> None:
        """Keep the websocket alive and dispatch messages."""
        delay = RECONNECT_MIN
        while not self._stopping:
            try:
                async with self._session.ws_connect(
                    self.url, protocols=(WS_SUBPROTOCOL,), heartbeat=30, timeout=30
                ) as ws:
                    self._ws = ws
                    self.connected.set()
                    delay = RECONNECT_MIN
                    _LOGGER.debug("Connected to Anova cloud")
                    async for msg in ws:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            self._handle(json.loads(msg.data))
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - keep the loop alive
                _LOGGER.warning("Anova websocket error: %s", err)
            finally:
                self._ws = None
                self.connected.clear()
            if self._stopping:
                return
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    def _handle(self, data: dict[str, Any]) -> None:
        """Dispatch one inbound message."""
        command = data.get("command")
        if command == "EVENT_APO_STATE":
            payload = data.get("payload") or {}
            cooker_id = payload.get("cookerId")
            if cooker_id:
                self.states[cooker_id] = payload
                if self._on_state:
                    self._on_state(cooker_id, payload)
        elif command == "EVENT_APO_WIFI_LIST":
            for device in data.get("payload") or []:
                self.devices[device["cookerId"]] = device
            self._devices_seen.set()
            if self._on_devices:
                self._on_devices(list(self.devices.values()))
        elif command == "RESPONSE":
            future = self._futures.pop(data.get("requestId", ""), None)
            if future is not None and not future.done():
                future.set_result(data.get("payload") or {})

    async def _send(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send a command and wait for its RESPONSE."""
        if self._ws is None or self._ws.closed:
            try:
                await asyncio.wait_for(self.connected.wait(), timeout=30)
            except (TimeoutError, asyncio.TimeoutError) as err:
                raise AnovaError("Not connected to the Anova cloud") from err
        assert self._ws is not None
        request_id = command["requestId"]
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._futures[request_id] = future
        await self._ws.send_json(command)
        try:
            result = await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT)
        except (TimeoutError, asyncio.TimeoutError) as err:
            self._futures.pop(request_id, None)
            raise AnovaError("No response from oven") from err
        if result.get("status") == "error":
            raise CommandError(result.get("error", "Unknown error"))
        return result

    async def async_start_cook(
        self, cooker_id: str, stages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Start a cook with the given stages."""
        return await self._send(
            {
                "command": "CMD_APO_START",
                "payload": {
                    "payload": {
                        "cookId": f"{PLATFORM_ID}-{uuid.uuid4()}",
                        "stages": stages,
                    },
                    "type": "CMD_APO_START",
                    "id": cooker_id,
                },
                "requestId": str(uuid.uuid4()),
            }
        )

    async def async_stop_cook(self, cooker_id: str) -> dict[str, Any]:
        """Stop the running cook."""
        return await self._send(
            {
                "command": "CMD_APO_STOP",
                "payload": {"type": "CMD_APO_STOP", "id": cooker_id},
                "requestId": str(uuid.uuid4()),
            }
        )
