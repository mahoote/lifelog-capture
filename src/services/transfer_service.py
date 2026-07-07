from __future__ import annotations

import logging
import threading

import uvicorn

from src.config import HTTP_HOST, HTTP_PORT
from src.services.http_server import app as http_app
from src.services.wifi_service import WifiService

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
        self._http_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start HTTP and begin monitoring transfer readiness."""
        logger.info("Starting transfer mode")

        self._stop_event.clear()
        self._start_http_server()

    def stop(self) -> None:
        """Stop HTTP."""
        logger.info("Stopping transfer mode")

        self._stop_event.set()
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
            logger.info("Stopped HTTP server")
