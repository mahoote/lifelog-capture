from __future__ import annotations

import logging
import threading
from enum import Enum
from time import sleep

import uvicorn

from src.configs.config import HTTP_HOST, HTTP_PORT
from src.services.http_server import app as http_app
from src.services.wifi_service import WifiService
from src.utils.internet_utils import has_internet_connection
from src.utils.led_utils import led_blink_amount, led_off, led_blink_loop, led_blink

logger = logging.getLogger(__name__)


class TransferBlinkStatus(Enum):
    """Enum for transfer blink status."""

    STARTING = "starting"
    RUNNING = "running"
    NO_INTERNET = "no_internet"


class TransferService:
    """Parent service for HTTP file transfer.

    This class starts and stops child services:
    - HTTP server for listing, downloading and acknowledging files

    It also provides the manifest and ack methods used by the HTTP routes.
    """

    def __init__(
            self,
    ):
        self.wifi_service = WifiService()
        http_app.state.wifi_service = self.wifi_service

        self._http_server: uvicorn.Server | None = None
        self._transfer_thread: threading.Thread | None = None
        self._transfer_blink_thread: threading.Thread | None = None
        self._stop_transfer_event = threading.Event()
        self._transfer_status = TransferBlinkStatus.STARTING

    def start(self) -> None:
        self._stop_transfer_event.clear()

        if not self._transfer_thread is None and self._transfer_thread.is_alive():
            return

        self._transfer_thread = threading.Thread(
            target=self._run_transfer,
            name="transfer",
            daemon=True,
        )
        self._transfer_thread.start()

        self._transfer_blink_thread = threading.Thread(
            target=self._transfer_blink_status,
            name="transfer-led-blink",
            daemon=True, )
        self._transfer_blink_thread.start()

    def stop(self) -> None:
        """Stop HTTP."""
        logger.info("Stopping transfer mode")

        self._stop_transfer_event.set()
        self._stop_http_server()

        if self._transfer_thread is not None:
            self._transfer_thread.join(timeout=3)
            self._transfer_thread = None

        if self._transfer_blink_thread is not None:
            self._transfer_blink_thread.join(timeout=1)
            self._transfer_blink_thread = None

    def _run_transfer(self) -> None:
        """Start HTTP and begin monitoring transfer readiness."""
        logger.info("Starting transfer mode")

        if not has_internet_connection():
            logger.error("No internet connection available. Transfer server will not start.")
            self._transfer_status = TransferBlinkStatus.NO_INTERNET
            return

        self._transfer_status = TransferBlinkStatus.RUNNING

        self._start_http_server()

    def _start_http_server(self) -> None:
        """Start the FastAPI HTTP server."""
        config = uvicorn.Config(
            http_app,
            host=HTTP_HOST,
            port=HTTP_PORT,
            log_level="info",
        )
        self._http_server = uvicorn.Server(config)
        self._http_server.run()

    def _stop_http_server(self) -> None:
        """Ask uvicorn to stop and wait briefly for the thread."""

        if self._http_server is not None:
            self._http_server.should_exit = True

    def _transfer_blink_status(self):
        """Blink the LED while the stop event is not set."""

        while not self._stop_transfer_event.is_set():

            match self._transfer_status:
                case TransferBlinkStatus.RUNNING:
                    led_blink(on_period_s=0.05,
                              off_period_s=0.05, )
                    
                case TransferBlinkStatus.STARTING:
                    led_blink_amount(4, 0.05, 0.05)
                    sleep(2)

                case TransferBlinkStatus.NO_INTERNET:
                    led_blink(on_period_s=0.5,
                              off_period_s=0.5, )
