from dataclasses import dataclass


@dataclass
class WifiStatus:
    """Current WiFi connection state for the Raspberry Pi."""

    connected: bool
    ssid: str | None
    ip: str | None
