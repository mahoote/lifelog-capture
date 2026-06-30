"""BLE service boundary for Lifelog Capture.

This file implements the Raspberry Pi side of the BLE setup channel.
The phone app talks to this service before it knows the Pi's IP address.
After WiFi has been configured, the phone uses the HTTP server for the
actual footage transfer.

Why BLE is used here
--------------------
BLE is slow for large files, but it is useful for setup and signalling.
This service should only handle small JSON messages, such as:

- asking the Pi to scan for WiFi networks
- sending WiFi credentials to the Pi
- reading the current WiFi connection status
- reading whether footage is ready to transfer
- sending small transfer control messages, such as ack commands

Why BlueZ D-Bus is used
-----------------------
On Linux, BLE peripheral mode is normally exposed through BlueZ. BlueZ is
controlled through D-Bus, so this file creates D-Bus objects that BlueZ can
register as a GATT application.

The important structure is:

1. Advertisement
   Makes the Pi visible as "Lifelog Glasses".

2. GATT service
   The top-level BLE service UUID.

3. GATT characteristics
   Small read, write, and notify endpoints that exchange JSON bytes.

Design goal
-----------
Keep the rest of the app away from BlueZ details. Other project code should
only need to create `BleService`, pass in `WifiService` and `TransferService`,
then call `start()` and `stop()`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import asdict, is_dataclass
from typing import Any

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next.service import ServiceInterface, dbus_property, method, signal

from src.config import (
    BLE_DEVICE_NAME,
    BLE_SERVICE_UUID,
    BLE_TRANSFER_COMMAND_UUID,
    BLE_TRANSFER_STATUS_UUID,
    BLE_WIFI_CREDENTIALS_UUID,
    BLE_WIFI_SCAN_UUID,
    BLE_WIFI_STATUS_UUID,
)
from src.services.transfer_service import TransferService
from src.services.wifi_service import WifiService

logger = logging.getLogger(__name__)

# BlueZ publishes its control API under this D-Bus service name.
# These constants are not UUIDs. They are D-Bus interface names and object paths.
# In most Raspberry Pi setups the BLE adapter path is /org/bluez/hci0.
BLUEZ_SERVICE_NAME = "org.bluez"
ADAPTER_PATH = "/org/bluez/hci0"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"

DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

# Object paths for our custom GATT app. BlueZ needs stable D-Bus paths so it can
# inspect the service, characteristics, and advertisement.
APP_PATH = "/com/lifelog/glasses"
SERVICE_PATH = f"{APP_PATH}/service0"
ADV_PATH = f"{APP_PATH}/advertisement0"


def _json_bytes(payload: dict[str, Any]) -> list[int]:
    """Encode a JSON payload into the byte-array format BlueZ expects.

    BlueZ represents characteristic values as an array of unsigned bytes.
    `dbus-next` maps that to `list[int]`, so this helper converts a Python
    dictionary into compact UTF-8 JSON bytes.
    """

    return list(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _decode_json(value: list[int] | bytes | bytearray) -> dict[str, Any]:
    """Decode bytes written by the phone into a JSON object.

    The phone app writes UTF-8 JSON into BLE characteristics. BlueZ gives us
    the raw bytes. This helper validates that the decoded value is an object,
    since the rest of the code expects keys such as `type`, `ssid`, and
    `password`.
    """

    if isinstance(value, list):
        raw = bytes(value)
    else:
        raw = bytes(value)

    if not raw:
        return {}

    decoded = raw.decode("utf-8")
    parsed = json.loads(decoded)

    if not isinstance(parsed, dict):
        raise ValueError("BLE payload must be a JSON object")

    return parsed


def _serialise_value(value: Any) -> Any:
    """Convert project objects into JSON-friendly values.

    This is useful when a response contains dataclasses, enums, UUIDs, dates,
    or other objects that `json.dumps` cannot serialise directly.
    """

    if is_dataclass(value):
        return {key: _serialise_value(item) for key, item in asdict(value).items()}

    if hasattr(value, "value"):
        return value.value

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if isinstance(value, dict):
        return {key: _serialise_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_serialise_value(item) for item in value]

    return value


class Application(ServiceInterface):
    """D-Bus ObjectManager for the BLE GATT application.

    BlueZ does not discover our characteristics by importing Python code.
    Instead, it asks this object for a map of managed D-Bus objects. That map
    says which GATT services and characteristics exist, and what properties
    each one has.
    """

    def __init__(self, bus: MessageBus):
        super().__init__(DBUS_OM_IFACE)
        self.bus = bus
        self.managed_objects: dict[str, dict[str, dict[str, Variant]]] = {}

    def add_object(self, path: str, interfaces: dict[str, dict[str, Variant]]) -> None:
        self.managed_objects[path] = interfaces

    @method()
    def GetManagedObjects(self) -> "a{oa{sa{sv}}}":
        return self.managed_objects


class Advertisement(ServiceInterface):
    """BLE advertisement shown to nearby devices.

    This is what makes the Pi appear in BLE scans as `BLE_DEVICE_NAME`.
    The advertisement also includes the main service UUID so the phone can
    filter for Lifelog devices rather than showing every BLE device nearby.
    """

    def __init__(self, service_uuid: str):
        super().__init__(LE_ADVERTISEMENT_IFACE)
        self.service_uuid = service_uuid

    @dbus_property()
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property()
    def ServiceUUIDs(self) -> "as":
        return [self.service_uuid]

    @dbus_property()
    def LocalName(self) -> "s":
        return BLE_DEVICE_NAME

    @dbus_property()
    def IncludeTxPower(self) -> "b":
        return True

    @method()
    def Release(self) -> None:
        logger.info("BLE advertisement released")

    def properties(self) -> dict[str, Variant]:
        return {
            "Type": Variant("s", self.Type),
            "ServiceUUIDs": Variant("as", self.ServiceUUIDs),
            "LocalName": Variant("s", self.LocalName),
            "IncludeTxPower": Variant("b", self.IncludeTxPower),
        }


class GattService(ServiceInterface):
    """Top-level GATT service.

    A GATT service groups related BLE characteristics. Here, all setup and
    transfer-signalling characteristics live under one Lifelog service UUID.
    """

    def __init__(self, uuid: str, primary: bool = True):
        super().__init__(GATT_SERVICE_IFACE)
        self.uuid = uuid
        self.primary = primary

    @dbus_property()
    def UUID(self) -> "s":
        return self.uuid

    @dbus_property()
    def Primary(self) -> "b":
        return self.primary

    @dbus_property()
    def Includes(self) -> "ao":
        return []

    def properties(self) -> dict[str, Variant]:
        return {
            "UUID": Variant("s", self.UUID),
            "Primary": Variant("b", self.Primary),
            "Includes": Variant("ao", self.Includes),
        }


class JsonCharacteristic(ServiceInterface):
    """Base class for characteristics that send and receive JSON.

    Most characteristics in this service follow the same pattern:

    - store a current value as bytes
    - return that value when the phone reads the characteristic
    - optionally accept writes from the phone
    - optionally notify the phone when the value changes

    Subclasses override `ReadValue` or `WriteValue` when they need behaviour
    beyond simply storing bytes.
    """

    def __init__(
        self,
        *,
        path: str,
        uuid: str,
        flags: list[str],
        service_path: str,
    ):
        super().__init__(GATT_CHRC_IFACE)
        self.path = path
        self.uuid = uuid
        self.flags = flags
        self.service_path = service_path
        self.notifying = False
        self._value: list[int] = []

    @dbus_property()
    def UUID(self) -> "s":
        return self.uuid

    @dbus_property()
    def Service(self) -> "o":
        return self.service_path

    @dbus_property()
    def Flags(self) -> "as":
        return self.flags

    @dbus_property()
    def Value(self) -> "ay":
        return self._value

    @method()
    def ReadValue(self, options: "a{sv}") -> "ay":
        return self._value

    @method()
    def WriteValue(self, value: "ay", options: "a{sv}") -> None:
        self._value = list(value)

    @method()
    def StartNotify(self) -> None:
        self.notifying = True

    @method()
    def StopNotify(self) -> None:
        self.notifying = False

    @signal()
    def PropertiesChanged(self, interface: "s", changed: "a{sv}", invalidated: "as") -> None:
        pass

    def set_json(self, payload: dict[str, Any]) -> None:
        self._value = _json_bytes(payload)

        if self.notifying:
            self.PropertiesChanged(
                GATT_CHRC_IFACE,
                {"Value": Variant("ay", self._value)},
                [],
            )

    def properties(self) -> dict[str, Variant]:
        return {
            "UUID": Variant("s", self.UUID),
            "Service": Variant("o", self.Service),
            "Flags": Variant("as", self.Flags),
            "Value": Variant("ay", self.Value),
        }


class WifiScanCharacteristic(JsonCharacteristic):
    """Characteristic used by the phone to request nearby WiFi networks.

    The phone can either read this characteristic directly or write a
    `wifi_scan_request` message. In both cases, the Pi responds with a
    `wifi_scan_result` payload containing an SSID list.
    """

    def __init__(self, *, wifi_service: WifiService):
        super().__init__(
            path=f"{SERVICE_PATH}/char0",
            uuid=BLE_WIFI_SCAN_UUID,
            flags=["read", "write"],
            service_path=SERVICE_PATH,
        )
        self.wifi_service = wifi_service

    def ReadValue(self, options: "a{sv}") -> "ay":
        self.set_json(
            {
                "type": "wifi_scan_result",
                "ssids": self.wifi_service.scan_networks(),
            }
        )
        return self._value

    def WriteValue(self, value: "ay", options: "a{sv}") -> None:
        payload = _decode_json(value)

        if payload.get("type") != "wifi_scan_request":
            raise ValueError("Expected wifi_scan_request")

        self.set_json(
            {
                "type": "wifi_scan_result",
                "ssids": self.wifi_service.scan_networks(),
            }
        )


class WifiCredentialsCharacteristic(JsonCharacteristic):
    """Characteristic used to receive WiFi credentials from the phone.

    The expected payload is:

    {"type": "wifi_credentials", "ssid": "...", "password": "..."}

    After trying to connect, this characteristic updates the WiFi status
    characteristic. If the connection succeeds, it also updates the transfer
    status so the phone can immediately discover the HTTP IP and file count.
    """

    def __init__(
        self,
        *,
        wifi_service: WifiService,
        status_characteristic: JsonCharacteristic,
        transfer_characteristic: JsonCharacteristic,
        transfer_service: TransferService,
    ):
        super().__init__(
            path=f"{SERVICE_PATH}/char1",
            uuid=BLE_WIFI_CREDENTIALS_UUID,
            flags=["write"],
            service_path=SERVICE_PATH,
        )
        self.wifi_service = wifi_service
        self.status_characteristic = status_characteristic
        self.transfer_characteristic = transfer_characteristic
        self.transfer_service = transfer_service

    def WriteValue(self, value: "ay", options: "a{sv}") -> None:
        payload = _decode_json(value)

        ssid = payload.get("ssid")
        password = payload.get("password")

        if payload.get("type") != "wifi_credentials":
            raise ValueError("Expected wifi_credentials")

        if not isinstance(ssid, str) or not isinstance(password, str):
            raise ValueError("ssid and password must be strings")

        connected = self.wifi_service.connect(ssid, password)
        wifi_status = self.wifi_service.get_status()

        status_payload = {
            "type": "wifi_status",
            "connected": connected and wifi_status.connected,
            "ssid": wifi_status.ssid,
            "ip": wifi_status.ip,
        }
        self.status_characteristic.set_json(status_payload)

        if status_payload["connected"]:
            self.transfer_characteristic.set_json(_build_transfer_ready_payload(self.wifi_service, self.transfer_service))


class TransferCommandCharacteristic(JsonCharacteristic):
    """Characteristic for small transfer control commands.

    The heavy transfer work happens through HTTP. This BLE characteristic is
    only for small control messages, such as asking whether transfer is ready
    or acknowledging a transferred file.
    """

    def __init__(
        self,
        *,
        transfer_service: TransferService,
        transfer_characteristic: JsonCharacteristic,
        wifi_service: WifiService,
    ):
        super().__init__(
            path=f"{SERVICE_PATH}/char4",
            uuid=BLE_TRANSFER_COMMAND_UUID,
            flags=["write"],
            service_path=SERVICE_PATH,
        )
        self.transfer_service = transfer_service
        self.transfer_characteristic = transfer_characteristic
        self.wifi_service = wifi_service

    def WriteValue(self, value: "ay", options: "a{sv}") -> None:
        payload = _decode_json(value)
        command_type = payload.get("type")

        if command_type == "transfer_status_request":
            self.transfer_characteristic.set_json(_build_transfer_ready_payload(self.wifi_service, self.transfer_service))
            return

        if command_type == "ack":
            file_id = payload.get("file_id")

            if not isinstance(file_id, str):
                raise ValueError("file_id must be a string")

            ok = self.transfer_service.acknowledge(file_id)
            self.transfer_characteristic.set_json(
                {
                    "type": "ack_result",
                    "file_id": file_id,
                    "ok": ok,
                }
            )
            return

        raise ValueError("Unsupported transfer command")


def _build_wifi_status_payload(wifi_service: WifiService) -> dict[str, Any]:
    """Build the JSON payload returned by the WiFi status characteristic."""

    status = wifi_service.get_status()
    return {
        "type": "wifi_status",
        "connected": status.connected,
        "ssid": status.ssid,
        "ip": status.ip,
    }


def _build_transfer_ready_payload(
    wifi_service: WifiService,
    transfer_service: TransferService,
) -> dict[str, Any]:
    """Build the JSON payload telling the phone that HTTP transfer can begin.

    The phone needs the Pi IP address to call the HTTP server. It also gets a
    file count so it can decide whether to show a transfer prompt.
    """

    wifi_status = wifi_service.get_status()
    pending_items = transfer_service.list_pending_items()

    return {
        "type": "transfer_ready",
        "ssid": wifi_status.ssid,
        "ip": wifi_status.ip,
        "file_count": len(pending_items),
    }


class BleService:
    """Public lifecycle wrapper for the BLE subsystem.

    This is the only class the rest of the app should normally use. It hides
    the D-Bus event loop, BlueZ registration, and BLE object creation behind a
    simple `start()` and `stop()` API.

    The service runs in a background thread because the main app already has
    its own lifecycle and worker threads. Running BLE in its own thread keeps
    the async D-Bus loop from blocking capture, storage, or HTTP work.
    """

    def __init__(
        self,
        *,
        wifi_service: WifiService,
        transfer_service: TransferService,
    ):
        self.wifi_service = wifi_service
        self.transfer_service = transfer_service
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._bus: MessageBus | None = None

    def start(self) -> None:
        """Start BLE advertising and GATT serving in a background thread."""

        # Avoid creating two BLE event loops if start is called twice.
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._run_thread,
            name="ble-service",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the BLE loop and wait briefly for the background thread."""

        if self._loop is None or self._stop_event is None:
            return

        self._loop.call_soon_threadsafe(self._stop_event.set)

        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run_thread(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        """Register the BLE app with BlueZ and keep status notifications fresh."""

        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()

        # BLE control lives on the system bus, not the user session bus.
        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        app = Application(self._bus)
        service = GattService(BLE_SERVICE_UUID)

        wifi_status_char = JsonCharacteristic(
            path=f"{SERVICE_PATH}/char2",
            uuid=BLE_WIFI_STATUS_UUID,
            flags=["read", "notify"],
            service_path=SERVICE_PATH,
        )
        wifi_status_char.set_json(_build_wifi_status_payload(self.wifi_service))

        transfer_status_char = JsonCharacteristic(
            path=f"{SERVICE_PATH}/char3",
            uuid=BLE_TRANSFER_STATUS_UUID,
            flags=["read", "notify"],
            service_path=SERVICE_PATH,
        )
        transfer_status_char.set_json(_build_transfer_ready_payload(self.wifi_service, self.transfer_service))

        # Characteristic order does not matter to BLE, but stable paths make
        # debugging easier. char0 to char4 are defined in one predictable list.
        chars: list[JsonCharacteristic] = [
            WifiScanCharacteristic(wifi_service=self.wifi_service),
            WifiCredentialsCharacteristic(
                wifi_service=self.wifi_service,
                status_characteristic=wifi_status_char,
                transfer_characteristic=transfer_status_char,
                transfer_service=self.transfer_service,
            ),
            wifi_status_char,
            transfer_status_char,
            TransferCommandCharacteristic(
                transfer_service=self.transfer_service,
                transfer_characteristic=transfer_status_char,
                wifi_service=self.wifi_service,
            ),
        ]

        self._bus.export(APP_PATH, app)
        self._bus.export(SERVICE_PATH, service)

        app.add_object(SERVICE_PATH, {GATT_SERVICE_IFACE: service.properties()})

        for char in chars:
            self._bus.export(char.path, char)
            app.add_object(char.path, {GATT_CHRC_IFACE: char.properties()})

        advertisement = Advertisement(BLE_SERVICE_UUID)
        self._bus.export(ADV_PATH, advertisement)

        introspection = await self._bus.introspect(BLUEZ_SERVICE_NAME, ADAPTER_PATH)
        adapter = self._bus.get_proxy_object(BLUEZ_SERVICE_NAME, ADAPTER_PATH, introspection)

        gatt_manager = adapter.get_interface(GATT_MANAGER_IFACE)
        advertising_manager = adapter.get_interface(LE_ADVERTISING_MANAGER_IFACE)

        # Hand the GATT app and advertisement to BlueZ. After these calls,
        # the phone should be able to discover and connect to the Pi.
        await gatt_manager.call_register_application(APP_PATH, {})
        await advertising_manager.call_register_advertisement(ADV_PATH, {})

        logger.info("BLE service started as %s", BLE_DEVICE_NAME)

        try:
            # Refresh status every few seconds. If the phone subscribed with
            # notifications, it receives updates without polling.
            while not self._stop_event.is_set():
                wifi_status_char.set_json(_build_wifi_status_payload(self.wifi_service))
                transfer_status_char.set_json(_build_transfer_ready_payload(self.wifi_service, self.transfer_service))
                await asyncio.wait_for(self._stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass
        finally:
            try:
                await advertising_manager.call_unregister_advertisement(ADV_PATH)
            except Exception:
                logger.exception("Failed to unregister BLE advertisement")

            try:
                await gatt_manager.call_unregister_application(APP_PATH)
            except Exception:
                logger.exception("Failed to unregister BLE GATT application")

            logger.info("BLE service stopped")
