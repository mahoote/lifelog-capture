"""BLE setup and signalling service for Lifelog Capture.

This service exposes the Raspberry Pi as a BLE peripheral called
"Lifelog Glasses". The mobile app uses this channel before it knows the Pi's
IP address.

BLE responsibilities:
- scan available WiFi networks
- receive WiFi credentials from the phone
- report current WiFi status and IP address
- report whether footage is ready for HTTP transfer
- receive small transfer commands, such as transfer status request or ack

BLE is not used for the video or photo bytes. Large file transfer should stay
on the local HTTP API because BLE is too slow for footage.
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
    BLE_TRANSFER_COMMAND_UUID,
    BLE_TRANSFER_STATUS_UUID,
    BLE_WIFI_CREDENTIALS_UUID,
    BLE_WIFI_SCAN_UUID,
    BLE_WIFI_STATUS_UUID,
)
from src.drivers.ble_driver import BleCharacteristicConfig, BleDriver
from src.utils.ble_utils import decode_json, json_bytes
from src.services.transfer_service import TransferService
from src.services.wifi_service import WifiService

logger = logging.getLogger(__name__)


class BleService:
    """Application-level BLE lifecycle and command handler.

    The service runs in a background thread so it does not block the main
    capture app. Internally it uses BleDriver, which hides the Bless API.
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
        """Thread entry point for the asyncio BLE loop."""

        asyncio.run(self._run())

    async def _run(self) -> None:
        """Start the driver and periodically publish fresh status values."""

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
                await self._publish_status()
                await asyncio.wait_for(self._stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            # wait_for raises TimeoutError during the normal periodic refresh loop.
            # The next loop iteration will publish status again.
            pass
        finally:
            await self._driver.stop()
            logger.info("BLE service stopped")

    def _characteristics(self) -> list[BleCharacteristicConfig]:
        """Define the GATT characteristics exposed by the Pi."""

        return [
            BleCharacteristicConfig(
                uuid=BLE_WIFI_SCAN_UUID,
                properties=GATTCharacteristicProperties.read | GATTCharacteristicProperties.write,
                permissions=GATTAttributePermissions.readable | GATTAttributePermissions.writeable,
                initial_value=json_bytes(self._wifi_scan_payload()),
            ),
            BleCharacteristicConfig(
                uuid=BLE_WIFI_CREDENTIALS_UUID,
                properties=GATTCharacteristicProperties.write,
                permissions=GATTAttributePermissions.writeable,
                initial_value=json_bytes({}),
            ),
            BleCharacteristicConfig(
                uuid=BLE_WIFI_STATUS_UUID,
                properties=GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
                permissions=GATTAttributePermissions.readable,
                initial_value=json_bytes(self._wifi_status_payload()),
            ),
            BleCharacteristicConfig(
                uuid=BLE_TRANSFER_STATUS_UUID,
                properties=GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
                permissions=GATTAttributePermissions.readable,
                initial_value=json_bytes(self._transfer_ready_payload()),
            ),
            BleCharacteristicConfig(
                uuid=BLE_TRANSFER_COMMAND_UUID,
                properties=GATTCharacteristicProperties.write,
                permissions=GATTAttributePermissions.writeable,
                initial_value=json_bytes({}),
            ),
        ]

    def _read_request(self, characteristic_uuid: str, current_value: bytearray) -> bytearray:
        """Return a fresh value when the phone reads a characteristic."""

        if characteristic_uuid == BLE_WIFI_SCAN_UUID:
            return json_bytes(self._wifi_scan_payload())

        if characteristic_uuid == BLE_WIFI_STATUS_UUID:
            return json_bytes(self._wifi_status_payload())

        if characteristic_uuid == BLE_TRANSFER_STATUS_UUID:
            return json_bytes(self._transfer_ready_payload())

        return current_value

    def _write_request(self, characteristic_uuid: str, value: bytearray) -> None:
        """Handle commands written by the phone."""

        payload = decode_json(value)

        if characteristic_uuid == BLE_WIFI_SCAN_UUID:
            self._handle_wifi_scan_request(payload)
            return

        if characteristic_uuid == BLE_WIFI_CREDENTIALS_UUID:
            self._handle_wifi_credentials(payload)
            return

        if characteristic_uuid == BLE_TRANSFER_COMMAND_UUID:
            self._handle_transfer_command(payload)
            return

        raise ValueError("Unsupported BLE write")

    def _handle_wifi_scan_request(self, payload: dict[str, Any]) -> None:
        """Validate a WiFi scan request.

        Reads from BLE_WIFI_SCAN_UUID already return the SSID list. A write to
        this characteristic is treated as a command to refresh the scan result.
        """

        if payload.get("type") != "wifi_scan_request":
            raise ValueError("Expected wifi_scan_request")

        self._schedule_status_publish()

    def _handle_wifi_credentials(self, payload: dict[str, Any]) -> None:
        """Connect the Pi to WiFi using credentials sent by the phone."""

        ssid = payload.get("ssid")
        password = payload.get("password")

        if payload.get("type") != "wifi_credentials":
            raise ValueError("Expected wifi_credentials")

        if not isinstance(ssid, str) or not isinstance(password, str):
            raise ValueError("ssid and password must be strings")

        self.wifi_service.connect(ssid, password)
        self._schedule_status_publish()

    def _handle_transfer_command(self, payload: dict[str, Any]) -> None:
        """Handle small transfer commands sent over BLE."""

        command_type = payload.get("type")

        if command_type == "transfer_status_request":
            self._schedule_status_publish()
            return

        if command_type == "ack":
            file_id = payload.get("file_id")

            if not isinstance(file_id, str):
                raise ValueError("file_id must be a string")

            self.transfer_service.acknowledge(file_id)
            self._schedule_status_publish()
            return

        raise ValueError("Unsupported transfer command")

    def _schedule_status_publish(self) -> None:
        """Publish status from sync callbacks without blocking Bless."""

        if self._loop is None:
            return

        asyncio.run_coroutine_threadsafe(self._publish_status(), self._loop)

    async def _publish_status(self) -> None:
        """Update notify characteristics with the latest app state."""

        if self._driver is None:
            return

        await self._driver.update_value(
            BLE_WIFI_STATUS_UUID,
            json_bytes(self._wifi_status_payload()),
        )
        await self._driver.update_value(
            BLE_TRANSFER_STATUS_UUID,
            json_bytes(self._transfer_ready_payload()),
        )

    def _wifi_scan_payload(self) -> dict[str, Any]:
        """Build the WiFi scan response payload."""

        return {
            "type": "wifi_scan_result",
            "ssids": self.wifi_service.scan_networks(),
        }

    def _wifi_status_payload(self) -> dict[str, Any]:
        """Build the current WiFi status payload."""

        status = self.wifi_service.get_status()

        return {
            "type": "wifi_status",
            "connected": status.connected,
            "ssid": status.ssid,
            "ip": status.ip,
        }

    def _transfer_ready_payload(self) -> dict[str, Any]:
        """Build the transfer readiness payload used by the phone."""

        wifi_status = self.wifi_service.get_status()
        pending_items = self.transfer_service.list_pending_items()

        return {
            "type": "transfer_ready",
            "ssid": wifi_status.ssid,
            "ip": wifi_status.ip,
            "file_count": len(pending_items),
        }
