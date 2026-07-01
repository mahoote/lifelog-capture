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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bless import BlessServer, GATTAttributePermissions, GATTCharacteristicProperties


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

        self.server = BlessServer(name=self.device_name)
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

        await self.server.stop()
        self.server = None

    async def update_value(self, characteristic_uuid: str, value: bytearray) -> None:
        """Update a characteristic value.

        For notify characteristics, Bless also sends a notification to subscribed
        central devices when the backend supports it.
        """

        if self.server is None:
            return

        await self.server.update_value(self.service_uuid, characteristic_uuid, value)

    def _handle_read(self, characteristic: Any, **kwargs: Any) -> bytearray:
        """Bless read callback.

        Bless passes a characteristic object. The service layer only needs the
        UUID and the current value, so this method adapts the callback shape.
        """

        uuid = str(characteristic.uuid)
        current_value = bytearray(characteristic.value or bytearray())
        return self.on_read(uuid, current_value)

    def _handle_write(self, characteristic: Any, value: bytearray, **kwargs: Any) -> None:
        """Bless write callback.

        The write payload is forwarded to the service layer where command
        validation and application behaviour happen.
        """

        uuid = str(characteristic.uuid)
        self.on_write(uuid, bytearray(value))
