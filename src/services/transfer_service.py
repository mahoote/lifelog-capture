from __future__ import annotations

import logging
import threading
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
        http_app.state.wifi_service = self.wifi_service

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

    def stop(self) -> None:
        """Stop BLE, stop HTTP."""

        self._stop_event.set()
        self.ble_service.stop()
        self._stop_http_server()

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
