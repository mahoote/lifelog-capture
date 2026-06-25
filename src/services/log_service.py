"""
Daily usage logging for the lifelog glasses.

The service keeps one text file per day in the root logs folder.
It only writes to disk when footage is taken, so the app avoids constant file IO.
"""

from __future__ import annotations

from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any

from src.services.motion_service import MotionState


class LogService:
    def __init__(self, motion_detector: Any, logs_dir: str | Path = "logs"):
        self.motion_detector = motion_detector
        self.logs_dir = Path(logs_dir)
        self._last_update_at: datetime | None = datetime.now()

    def record_footage_taken(self, capture_mode_enabled: bool = True) -> None:
        """
        Update the daily usage log after a photo or video has been captured.

        The time since the previous update is added to:
        - total seconds in capture mode
        - the current motion state's total

        If capture mode is disabled, no file is written and the timer is reset.
        """
        now = datetime.now()

        if not capture_mode_enabled:
            self._last_update_at = now
            return

        if self._last_update_at is None:
            self._last_update_at = now
            return

        if now <= self._last_update_at:
            return

        motion_state = self._get_motion_state_name()
        self._add_interval(self._last_update_at, now, motion_state)
        self._last_update_at = now

    def pause_capture_mode(self) -> None:
        """
        Reset the timer when capture mode is disabled.

        This does not write to disk. It prevents disabled time from being counted
        when capture mode is later enabled again.
        """
        self._last_update_at = datetime.now()

    def _add_interval(self, start: datetime, end: datetime, motion_state: str) -> None:
        """Split an interval across day boundaries and add each part to its day."""
        current = start

        while current < end:
            next_midnight = datetime.combine(
                current.date() + timedelta(days=1),
                datetime_time.min,
            )
            segment_end = min(end, next_midnight)
            seconds = int((segment_end - current).total_seconds())

            if seconds > 0:
                self._add_seconds_to_day(current.date().isoformat(), motion_state, seconds)

            current = segment_end

    def _add_seconds_to_day(self, day: str, motion_state: str, seconds: int) -> None:
        totals = self._read_day_log(day)

        totals["total"] += seconds
        totals[motion_state] += seconds

        self._write_day_log(day, totals)

    def _read_day_log(self, day: str) -> dict[str, int]:
        path = self._day_log_path(day)

        totals = {
            "total": 0,
            MotionState.IDLE.value: 0,
            MotionState.DEFAULT.value: 0,
            MotionState.ACTIVE.value: 0,
        }

        if not path.exists():
            return totals

        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue

            try:
                seconds = int(value.strip())
            except ValueError:
                continue

            match key.strip().lower():
                case "total seconds in capture mode":
                    totals["total"] = seconds
                case "seconds idle":
                    totals[MotionState.IDLE.value] = seconds
                case "seconds default":
                    totals[MotionState.DEFAULT.value] = seconds
                case "seconds active":
                    totals[MotionState.ACTIVE.value] = seconds

        return totals

    def _write_day_log(self, day: str, totals: dict[str, int]) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        path = self._day_log_path(day)

        content = (
            f"total seconds in capture mode: {totals['total']}\n"
            f"seconds idle: {totals[MotionState.IDLE.value]}\n"
            f"seconds default: {totals[MotionState.DEFAULT.value]}\n"
            f"seconds active: {totals[MotionState.ACTIVE.value]}\n"
        )

        path.write_text(content, encoding="utf-8")

    def _day_log_path(self, day: str) -> Path:
        return self.logs_dir / f"{day}.txt"

    def _get_motion_state_name(self) -> str:
        state = self.motion_detector.state

        if isinstance(state, MotionState):
            return state.value

        state_name = str(state).lower()

        if state_name in {
            MotionState.IDLE.value,
            MotionState.DEFAULT.value,
            MotionState.ACTIVE.value,
        }:
            return state_name

        return MotionState.DEFAULT.value
