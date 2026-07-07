"""Small Bless based BLE driver.

This module is the only place that should know about the Bless package.
The rest of the application can work with plain Python callbacks and byte
payloads instead of BLE library objects.

The driver is intentionally thin:
- create and start the BLE GATT server
- register services and characteristics
- route read and write requests back to the service layer
- update characteristic values for read and notify characteristics

Keeping this wrapper separate makes it easier to replace Bless later if the
Raspberry Pi needs a lower level BlueZ implementation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from bless import BlessServer, GATTAttributePermissions, GATTCharacteristicProperties

logger = logging.getLogger(__name__)

ReadHandler = Callable[[str, bytearray], bytearray]
WriteHandler = Callable[[str, bytearray], None]


@dataclass(frozen=True)
class BleCharacteristicConfig:
    """Configuration for one GATT characteristic.

    Attributes:
        uuid: Characteristic UUID.
        properties: Bless characteristic properties, such as read, write, notify.
        permissions: Bless attribute permissions, such as readable or writeable.
        initial_value: Initial bytes stored in the characteristic.
    """

    uuid: str
    properties: GATTCharacteristicProperties
    permissions: GATTAttributePermissions
    initial_value: bytearray


class BleDriver:
    """Driver wrapper around BlessServer.

    BleService owns the application behaviour. BleDriver owns the BLE server
    mechanics. This keeps connection overhead out of the app-level service.
    """

    def __init__(
            self,
            *,
            device_name: str,
            service_uuid: str,
            on_read: ReadHandler,
            on_write: WriteHandler,
    ):
        self.device_name = device_name
        self.service_uuid = service_uuid
        self.on_read = on_read
        self.on_write = on_write
        self.server: BlessServer | None = None

    async def start(self, characteristics: list[BleCharacteristicConfig]) -> None:
        """Create the Bless server, add the GATT service and start advertising."""

        loop = asyncio.get_running_loop()
        
        self.server = BlessServer(name=self.device_name, loop=loop)
        self.server.read_request_func = self._handle_read
        self.server.write_request_func = self._handle_write

        await self.server.add_new_service(self.service_uuid)

        for characteristic in characteristics:
            await self.server.add_new_characteristic(
                self.service_uuid,
                characteristic.uuid,
                characteristic.properties,
                characteristic.initial_value,
                characteristic.permissions,
            )

        await self.server.start()

    async def stop(self) -> None:
        """Stop advertising and shut down the Bless server."""

        if self.server is None:
            return

        try:
            await self.server.stop()
        except Exception:
            logger.warning("BLE server stop failed; continuing shutdown", exc_info=True)
        self.server = None

    async def update_value(self, characteristic_uuid: str, value: bytearray) -> None:
        """Update a characteristic value.

        For notify characteristics, Bless also sends a notification to subscribed
        central devices when the backend supports it.
        """

        if self.server is None:
            return

        await self.server.update_value(self.service_uuid, characteristic_uuid, value)

    def _handle_read(self, characteristic: Any) -> bytearray:
        """Bless read callback.

        Bless passes a characteristic object. The service layer only needs the
        UUID and the current value, so this method adapts the callback shape.
        """

        uuid = str(characteristic.uuid)
        current_value = bytearray(characteristic.value or bytearray())
        return self.on_read(uuid, current_value)

    def _handle_write(self, characteristic: Any, value: bytearray) -> None:
        """Bless write callback.

        The write payload is forwarded to the service layer where command
        validation and application behaviour happen.
        """

        uuid = str(characteristic.uuid)
        self.on_write(uuid, bytearray(value))

    def has_subscribers(self, characteristic_uuid: str) -> bool:
        """Return True if any central is subscribed to the given characteristic.

        BlessServer's public API for subscribers varies across versions and is
        implementation-specific. Probe common attributes and methods defensively
        so this helper works across multiple Bless releases without hard
        depending on internals.
        """

        if self.server is None:
            return False

        try:
            # Common attribute name: subscribers (dict or list)
            subs = getattr(self.server, "subscribers", None)
            if subs:
                if isinstance(subs, dict):
                    # dict keyed by uuid or (service_uuid, uuid)
                    # Check for direct key match first.
                    if characteristic_uuid in subs:
                        return bool(subs[characteristic_uuid])
                    # Otherwise check values for any truthy entry.
                    return any(bool(v) for v in subs.values())
                if isinstance(subs, (list, set, tuple)):
                    return len(subs) > 0

            # Some BlessServer versions expose a helper method.
            get_subs = getattr(self.server, "get_subscribers", None)
            if callable(get_subs):
                try:
                    result = get_subs(self.service_uuid, characteristic_uuid)
                except TypeError:
                    # Fallback to single-arg signature
                    result = get_subs(characteristic_uuid)
                return bool(result)

            # Other possible attributes
            for attr in ("subscribed_devices", "subscribed_centrals", "connections"):
                val = getattr(self.server, attr, None)
                if val:
                    if isinstance(val, dict):
                        return any(bool(v) for v in val.values())
                    if isinstance(val, (list, set, tuple)):
                        return len(val) > 0

            return False
        except Exception:
            # Be conservative on errors and report no subscribers.
            return False
