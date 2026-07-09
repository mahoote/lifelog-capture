import socket
import logging

logger = logging.getLogger(__name__)


def has_internet_connection() -> bool:
    """Return True if the Pi can reach the internet."""
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=3):
            return True
    except OSError as exc:
        logger.info("Internet connection check failed: %s", exc)
        return False
