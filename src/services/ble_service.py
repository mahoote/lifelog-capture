"""
The Raspberry Pi advertises as a BLE peripheral called "Lifelog Glasses".
The phone app uses BLE only for setup and discovery, then uses HTTP for the
actual footage transfer.

Exposes three BLE characteristics:

1. WiFi scan, read only
   The phone reads this to get the nearby SSID list.

2. WiFi credentials, write only
   The phone writes SSID and password here so the Pi can join the same WiFi.

3. Device status, read and notify
   The phone reads or subscribes to this to get connection state, IP address
   and pending file count.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from bless import GATTAttributePermissions, GATTCharacteristicProperties

from src.config import (
    BLE_DEVICE_NAME,
    BLE_SERVICE_UUID,
    BLE_WIFI_CREDENTIALS_UUID,
    BLE_WIFI_SCAN_UUID,
    BLE_WIFI_STATUS_UUID,
)
from src.drivers.ble_driver import BleCharacteristicConfig, BleDriver
from src.services import storage
from src.services.wifi_service import WifiService
from src.utils.ble_utils import decode_json, json_bytes

logger = logging.getLogger(__name__)

# BLE_WIFI_STATUS_UUID is used as the single device status characteristic.
# It now includes both WiFi status and transfer readiness.
DEVICE_STATUS_UUID = BLE_WIFI_STATUS_UUID


class BleService:
    """Application-level BLE lifecycle and command handler.

    The Bless-specific code lives in BleDriver. This class only decides what
    the phone can read or write and how that maps onto the app services.
    """

    def __init__(
            self,
            *,
            wifi_service: WifiService
    ):
        self.wifi_service = wifi_service
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._driver: BleDriver | None = None

    def start(self) -> None:
        """Start BLE advertising and GATT serving in a background thread."""

        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=self._run_thread,
            name="ble-service",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop BLE and wait briefly for the background thread to exit."""

        if self._loop is None or self._stop_event is None:
            return

        self._loop.call_soon_threadsafe(self._stop_event.set)

        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run_thread(self) -> None:
        """Bridge the background thread into the asyncio BLE loop."""

        asyncio.run(self._run())

    async def _run(self) -> None:
        """Start the BLE driver and keep the device status value fresh."""

        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()

        self._driver = BleDriver(
            device_name=BLE_DEVICE_NAME,
            service_uuid=BLE_SERVICE_UUID,
            on_read=self._read_request,
            on_write=self._write_request,
        )

        await self._driver.start(self._characteristics())
        logger.info("BLE service started as %s", BLE_DEVICE_NAME)

        try:
            while not self._stop_event.is_set():
                await self._publish_device_status()
                await asyncio.wait_for(self._stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            # A timeout is expected during the periodic refresh loop.
            pass
        finally:
            await self._driver.stop()
            logger.info("BLE service stopped")

    def _characteristics(self) -> list[BleCharacteristicConfig]:
        """Define the simplified GATT API exposed by the Pi."""

        return [
            BleCharacteristicConfig(
                uuid=BLE_WIFI_SCAN_UUID,
                properties=GATTCharacteristicProperties.read,
                permissions=GATTAttributePermissions.readable,
                initial_value=json_bytes(self._wifi_scan_payload()),
            ),
            BleCharacteristicConfig(
                uuid=BLE_WIFI_CREDENTIALS_UUID,
                properties=GATTCharacteristicProperties.write,
                permissions=GATTAttributePermissions.writeable,
                initial_value=json_bytes({}),
            ),
            BleCharacteristicConfig(
                uuid=DEVICE_STATUS_UUID,
                properties=GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
                permissions=GATTAttributePermissions.readable,
                initial_value=json_bytes(self._device_status_payload()),
            ),
        ]

    def _read_request(self, characteristic_uuid: str, current_value: bytearray) -> bytearray:
        """Return a fresh value when the phone reads a characteristic."""

        if characteristic_uuid == BLE_WIFI_SCAN_UUID:
            return json_bytes(self._wifi_scan_payload())

        if characteristic_uuid == DEVICE_STATUS_UUID:
            return json_bytes(self._device_status_payload())

        return current_value

    def _write_request(self, characteristic_uuid: str, value: bytearray) -> None:
        """Handle commands written by the phone."""

        if characteristic_uuid != BLE_WIFI_CREDENTIALS_UUID:
            raise ValueError("Unsupported BLE write")

        self._handle_wifi_credentials(decode_json(value))

    def _handle_wifi_credentials(self, payload: dict[str, Any]) -> None:
        """Connect the Pi to WiFi using credentials sent by the phone."""

        ssid = payload.get("ssid")
        password = payload.get("password")

        if payload.get("type") != "wifi_credentials":
            raise ValueError("Expected wifi_credentials")

        if not isinstance(ssid, str) or not isinstance(password, str):
            raise ValueError("ssid and password must be strings")

        self.wifi_service.connect(ssid, password)
        self._schedule_device_status_publish()

    def _schedule_device_status_publish(self) -> None:
        """Publish status from a synchronous BLE callback."""

        if self._loop is None:
            return

        asyncio.run_coroutine_threadsafe(self._publish_device_status(), self._loop)

    async def _publish_device_status(self) -> None:
        """Update the notify characteristic with the latest device status."""

        if self._driver is None:
            return

        await self._driver.update_value(
            DEVICE_STATUS_UUID,
            json_bytes(self._device_status_payload()),
        )

    def is_phone_connected(self) -> bool:
        """Return True if a central (phone) is currently subscribed to the
        device status notify characteristic.

        This delegates to the driver which probes the underlying Bless server
        state defensively to avoid hard dependencies on library internals.
        """

        if self._driver is None:
            return False

        try:
            return self._driver.has_subscribers(DEVICE_STATUS_UUID)
        except Exception:
            return False

    def _wifi_scan_payload(self) -> dict[str, Any]:
        """Build the WiFi scan response payload."""

        return {
            "type": "wifi_scan_result",
            "ssids": self.wifi_service.scan_networks(),
        }

    def _device_status_payload(self) -> dict[str, Any]:
        """Build the combined WiFi and transfer status payload."""

        wifi_status = self.wifi_service.get_status()
        pending_items = storage.list_pending()

        return {
            "type": "device_status",
            "connected": wifi_status.connected,
            "ssid": wifi_status.ssid,
            "ip": wifi_status.ip,
            "file_count": len(pending_items),
        }
