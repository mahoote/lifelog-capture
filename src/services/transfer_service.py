from __future__ import annotations

import logging
import threading
from time import sleep

import uvicorn

from src.configs.config import HTTP_HOST, HTTP_PORT
from src.services.http_server import app as http_app
from src.services.wifi_service import WifiService
from src.utils.internet_utils import has_internet_connection
from src.utils.led_utils import led_blink_amount, led_off, led_blink_loop

logger = logging.getLogger(__name__)


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

    def start(self) -> None:
        self._transfer_thread = threading.Thread(
            target=self._run_transfer,
            name="transfer",
            daemon=True,
        )
        self._transfer_thread.start()

        self._transfer_blink_thread = threading.Thread(
            target=self._transfer_blink_loop,
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

        if self._transfer_blink_thread is not None:
            self._transfer_blink_thread.join(timeout=1)

    def _run_transfer(self) -> None:
        """Start HTTP and begin monitoring transfer readiness."""
        logger.info("Starting transfer mode")

        self._stop_transfer_event.clear()

        if not has_internet_connection():
            logger.error("No internet connection available. Transfer server will not start.")
            led_blink_loop(
                stop_event=self._stop_transfer_event,
                on_period_s=0.5,
                off_period_s=0.5,
            )
            return

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

    def _transfer_blink_loop(self):
        """Blink the LED while the stop event is not set."""

        while not self._stop_transfer_event.is_set():
            led_blink_amount(4, 0.05, 0.05)
            sleep(2)

        led_off()
