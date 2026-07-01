"""JSON payload helpers for the BLE setup channel.

BLE characteristic values are bytes. The phone and Pi exchange small JSON
objects encoded as UTF-8 bytes. These helpers keep the encoding and validation
in one place.
"""

from __future__ import annotations

import json
from typing import Any


def json_bytes(payload: dict[str, Any]) -> bytearray:
    """Encode a JSON object as compact UTF-8 bytes for BLE."""

    return bytearray(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def decode_json(value: bytes | bytearray | list[int]) -> dict[str, Any]:
    """Decode a BLE byte payload into a JSON object.

    Raises:
        ValueError: If the payload is not a JSON object.
    """

    raw = bytes(value)

    if not raw:
        return {}

    payload = json.loads(raw.decode("utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("BLE payload must be a JSON object")

    return payload
