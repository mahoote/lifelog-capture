import subprocess
import socket

from src.types.wifi_status import WifiStatus


class WifiService:
    """Service for reading and reconnecting Wi-Fi state."""

    def get_status(self) -> WifiStatus:
        """
        Read the current WiFi connection status.

        Returns:
            A WifiStatus object containing whether the Pi is connected,
            the active SSID and the current IP address when available.
        """
        ssid_result = subprocess.run(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            capture_output=True,
            text=True,
            check=False,
        )

        active_ssid = None

        for line in ssid_result.stdout.splitlines():
            if line.startswith("yes:"):
                active_ssid = line.split(":", 1)[1]
                break

        ip = self._get_ip_address()

        return WifiStatus(
            connected=active_ssid is not None and ip is not None,
            ssid=active_ssid,
            ip=ip,
        )

    def reconnect(self) -> bool:
        """Try to reconnect to a saved Wi-Fi network.

        NetworkManager stores previously configured Wi-Fi connections as
        connection profiles. This method asks NetworkManager to rescan, then
        tries to bring up each saved Wi-Fi profile until one works.

        Returns:
            True if a saved Wi-Fi profile was started, otherwise False.
        """
        subprocess.run(
            ["nmcli", "dev", "wifi", "rescan"],
            capture_output=True,
            text=True,
            check=False,
        )

        profiles_result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            capture_output=True,
            text=True,
            check=False,
        )

        if profiles_result.returncode != 0:
            return False

        wifi_profiles: list[str] = []

        for line in profiles_result.stdout.splitlines():
            name, separator, connection_type = line.rpartition(":")

            if not separator or connection_type != "802-11-wireless":
                continue

            wifi_profiles.append(name.replace("\\:", ":"))

        for profile in wifi_profiles:
            connect_result = subprocess.run(
                ["nmcli", "connection", "up", profile],
                capture_output=True,
                text=True,
                check=False,
            )

            if connect_result.returncode == 0:
                return True

        return False

    def _get_ip_address(self) -> str | None:
        """
        Get the Pi's active IPv4 address.

        A UDP socket is opened to infer which local interface would be used
        for outbound traffic. No data is sent to the remote address.

        Returns:
            The active local IPv4 address, or None if no address is available.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except OSError:
            return None
