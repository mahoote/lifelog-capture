"""
TransferService coordinates the local transfer flow. It owns the HTTP server
and BLE service lifecycle, then decides what the phone should do next:

1. If no phone is connected over BLE, advertise and wait for BLE.
2. If BLE is connected but WiFi is not connected, ask the phone to complete
   WiFi setup over BLE.
3. If BLE and WiFi are both connected, signal that HTTP transfer is ready.

The actual footage bytes are still transferred over HTTP. BLE is only used for
setup, connection state and readiness signalling.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import StrEnum

import uvicorn

from src.config import HTTP_HOST, HTTP_PORT
from src.services.ble_service import BleService
from src.services.http_server import app as http_app
from src.services.wifi_service import WifiService

logger = logging.getLogger(__name__)


class TransferStep(StrEnum):
    """High-level state used by the phone to decide what to do next."""

    WAITING_FOR_BLE = "waiting_for_ble"
    WAITING_FOR_WIFI = "waiting_for_wifi"
    READY_TO_TRANSFER = "ready_to_transfer"


@dataclass(frozen=True)
class TransferStatus:
    """Current transfer readiness state.

    Attributes:
        step: The next step in the transfer setup flow.
        ble_connected: True when a phone is connected over BLE.
        wifi_connected: True when the Pi is connected to WiFi and has an IP.
        ssid: Current WiFi SSID, if connected.
        ip: Current Pi IP address, if connected.
        file_count: Number of footage items waiting for transfer.
    """

    step: TransferStep
    ble_connected: bool
    wifi_connected: bool
    ssid: str | None
    ip: str | None
    file_count: int


class TransferService:
    """Parent service for BLE setup and HTTP file transfer.

    This class starts and stops both child services:
    - HTTP server for listing, downloading and acknowledging files
    - BLE service for WiFi setup and transfer readiness signalling

    It also provides the manifest and ack methods used by the HTTP routes.
    """

    def __init__(
            self,
    ):
        self.wifi_service = WifiService()
        self.ble_service = BleService(
            wifi_service=self.wifi_service
        )

        self._http_server: uvicorn.Server | None = None
        self._http_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start HTTP, start BLE and begin monitoring transfer readiness."""

        self._stop_event.clear()
        self._start_http_server()
        self.ble_service.start()
        self._start_monitor()

    def stop(self) -> None:
        """Stop BLE, stop HTTP and stop the readiness monitor."""

        self._stop_event.set()
        self.ble_service.stop()
        self._stop_http_server()

        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=3)

    def get_status(self) -> TransferStatus:
        """Return the current BLE, WiFi and transfer readiness state."""

        ble_connected = self.ble_service.is_connected()
        wifi_status = self.wifi_service.get_status()
        wifi_connected = wifi_status.connected and wifi_status.ip is not None
        file_count = len(self.list_pending_items())

        if not ble_connected:
            step = TransferStep.WAITING_FOR_BLE
        elif not wifi_connected:
            step = TransferStep.WAITING_FOR_WIFI
        else:
            step = TransferStep.READY_TO_TRANSFER

        return TransferStatus(
            step=step,
            ble_connected=ble_connected,
            wifi_connected=wifi_connected,
            ssid=wifi_status.ssid,
            ip=wifi_status.ip,
            file_count=file_count,
        )

    def build_ble_status_payload(self) -> dict[str, object]:
        """Build the single BLE status payload sent to the phone.

        BleService can call this method instead of duplicating readiness logic.
        """

        status = self.get_status()

        return {
            "type": "device_status",
            "step": status.step,
            "ble_connected": status.ble_connected,
            "wifi_connected": status.wifi_connected,
            "ssid": status.ssid,
            "ip": status.ip,
            "file_count": status.file_count,
            "ready_to_transfer": status.step == TransferStep.READY_TO_TRANSFER,
            "http_base_url": f"http://{status.ip}:{HTTP_PORT}" if status.ip else None,
        }

    def _start_http_server(self) -> None:
        """Start the FastAPI HTTP server in a background thread."""

        if self._http_thread is not None and self._http_thread.is_alive():
            return

        config = uvicorn.Config(
            http_app,
            host=HTTP_HOST,
            port=HTTP_PORT,
            log_level="info",
        )
        self._http_server = uvicorn.Server(config)
        self._http_thread = threading.Thread(
            target=self._http_server.run,
            name="http-server",
            daemon=True,
        )
        self._http_thread.start()

    def _stop_http_server(self) -> None:
        """Ask uvicorn to stop and wait briefly for the thread."""

        if self._http_server is not None:
            self._http_server.should_exit = True

        if self._http_thread is not None:
            self._http_thread.join(timeout=3)

    def _start_monitor(self) -> None:
        """Start a small monitor that publishes BLE status changes."""

        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return

        self._monitor_thread = threading.Thread(
            target=self._monitor_transfer_state,
            name="transfer-monitor",
            daemon=True,
        )
        self._monitor_thread.start()

    def _monitor_transfer_state(self) -> None:
        """Watch BLE and WiFi state, then notify the phone when ready.

        This keeps the phone informed even when the state changes outside a BLE
        write callback, for example when WiFi connects a few seconds after the
        credentials were written.
        """

        previous_payload: dict[str, object] | None = None

        while not self._stop_event.is_set():
            payload = self.build_ble_status_payload()

            if payload != previous_payload:
                self._publish_ble_status(payload)
                previous_payload = payload

            time.sleep(2)

    def _publish_ble_status(self, payload: dict[str, object]) -> None:
        """Send the latest status to the connected phone over BLE."""

        try:
            self.ble_service.publish_device_status(payload)
        except Exception:
            logger.exception("Failed to publish BLE transfer status")
