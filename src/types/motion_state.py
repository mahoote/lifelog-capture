from enum import Enum


class MotionState(str, Enum):
    IDLE = "idle"
    DEFAULT = "default"
    ACTIVE = "active"
