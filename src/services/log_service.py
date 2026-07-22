"""
Daily usage logging for the lifelog glasses.

The service keeps one text file per day in the root logs folder.
It tracks state durations in memory when the motion state changes, but only
writes to disk when footage is taken.
"""

from __future__ import annotations

from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path

from src.services.motion_service import MotionService
from src.types.motion_state import MotionState


class LogService:
    def __init__(self, motion_service: MotionService, logs_dir: str | Path = "logs"):
        self.motion_service = motion_service
        self.logs_dir = Path(logs_dir)

        self._capture_mode_enabled = True
        self._current_state = self._get_motion_state_name()
        self._last_accounted_at: datetime | None = datetime.now(timezone.utc)
        self._pending_totals = self._empty_totals()

    def record_motion_state_change(self, new_state: MotionState | str) -> None:
        """
        Track time spent in the previous state when the motion state changes.

        This only updates in-memory totals. It does not write to disk.
        """
        now = datetime.now(timezone.utc)
        new_state_name = self._normalise_motion_state(new_state)

        if self._last_accounted_at is None:
            self._last_accounted_at = now
            self._current_state = new_state_name
            return

        if self._capture_mode_enabled:
            self._add_interval_to_pending(
                start=self._last_accounted_at,
                end=now,
                motion_state=self._current_state,
            )

        self._last_accounted_at = now
        self._current_state = new_state_name

    def record_footage_taken(self, capture_mode_enabled: bool = True) -> None:
        """
        Flush the in-memory usage totals to the daily log file.

        This is called after a photo or video is captured. Before writing, it
        also accounts for the time since the previous state change or flush.
        """
        now = datetime.now(timezone.utc)

        if not capture_mode_enabled:
            self.pause_capture_mode()
            return

        self._capture_mode_enabled = True

        if self._last_accounted_at is not None:
            self._add_interval_to_pending(
                start=self._last_accounted_at,
                end=now,
                motion_state=self._current_state,
            )

        self._last_accounted_at = now
        self._flush_pending_totals()

    def pause_capture_mode(self) -> None:
        """
        Pause capture-mode accounting.

        This accounts for the time up to the pause in memory, but does not write
        to disk. The pending totals are written next time footage is taken.
        """
        now = datetime.now(timezone.utc)

        if self._capture_mode_enabled and self._last_accounted_at is not None:
            self._add_interval_to_pending(
                start=self._last_accounted_at,
                end=now,
                motion_state=self._current_state,
            )

        self._capture_mode_enabled = False
        self._last_accounted_at = now

    def resume_capture_mode(self) -> None:
        """
        Resume capture-mode accounting without counting the paused time.
        """
        self._capture_mode_enabled = True
        self._last_accounted_at = datetime.now(timezone.utc)
        self._current_state = self._get_motion_state_name()

    def _add_interval_to_pending(
            self,
            start: datetime,
            end: datetime,
            motion_state: str,
    ) -> None:
        """Split an interval across day boundaries and add each part in memory."""
        if end <= start:
            return

        current = start

        while current < end:
            next_midnight = datetime.combine(
                current.date() + timedelta(days=1),
                datetime_time.min,
            )
            segment_end = min(end, next_midnight)
            seconds = int((segment_end - current).total_seconds())

            if seconds > 0:
                day = current.date().isoformat()
                self._pending_totals.setdefault(day, self._empty_day_totals())
                self._pending_totals[day]["total"] += seconds
                self._pending_totals[day][motion_state] += seconds

            current = segment_end

    def _flush_pending_totals(self) -> None:
        """Read each affected daily file, add pending totals, and write it back."""
        for day, pending in self._pending_totals.items():
            if pending["total"] <= 0:
                continue

            totals = self._read_day_log(day)

            totals["total"] += pending["total"]
            totals[MotionState.IDLE.value] += pending[MotionState.IDLE.value]
            totals[MotionState.DEFAULT.value] += pending[MotionState.DEFAULT.value]
            totals[MotionState.ACTIVE.value] += pending[MotionState.ACTIVE.value]

            self._write_day_log(day, totals)

        self._pending_totals = self._empty_totals()

    def _read_day_log(self, day: str) -> dict[str, int]:
        path = self._day_log_path(day)
        totals = self._empty_day_totals()

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
        return self._normalise_motion_state(self.motion_service.state)

    @staticmethod
    def _normalise_motion_state(state: MotionState | str) -> str:
        if isinstance(state, MotionState):
            return state.value

        state_name = str(state).lower()

        if state_name.startswith("motionstate."):
            state_name = state_name.split(".", maxsplit=1)[1]

        if state_name in {
            MotionState.IDLE.value,
            MotionState.DEFAULT.value,
            MotionState.ACTIVE.value,
        }:
            return state_name

        return MotionState.DEFAULT.value

    @staticmethod
    def _empty_totals() -> dict[str, dict[str, int]]:
        return {}

    @staticmethod
    def _empty_day_totals() -> dict[str, int]:
        return {
            "total": 0,
            MotionState.IDLE.value: 0,
            MotionState.DEFAULT.value: 0,
            MotionState.ACTIVE.value: 0,
        }
