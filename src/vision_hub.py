"""Dual-Camera OpenCV Switchboard & 1.5-Second 'Dwell-to-Inspect' Watchdog."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import (
    DWELL_MOTION_SPIKE_THRESHOLD,
    DWELL_STILLNESS_THRESHOLD,
    DWELL_TO_INSPECT_SECONDS,
    RAW_CAPTURES_DIR,
)


@dataclass
class DualCaptureSnapshot:
    timestamp: float
    overhead_cam_id: int
    macro_cam_id: int
    zoom_level: float
    trigger_source: str  # "F14_FOOT_PEDAL", "VOICE_CMD", "DWELL_WATCHDOG"
    dwell_locked: bool
    summary: str


class VisionHub:
    """Manages Camera 0 (Overhead Wide PCB Cam) and Camera 1 (Macro Workstation Cam)."""

    def __init__(self, overhead_cam_id: int = 0, macro_cam_id: int = 1) -> None:
        self.overhead_cam_id = overhead_cam_id
        self.macro_cam_id = macro_cam_id
        self.zoom_level: float = 1.0
        self.dwell_timer_s: float = 0.0
        self.motion_spiked: bool = False
        self.snapshots: list[DualCaptureSnapshot] = []

    def adjust_macro_zoom(self, delta: float) -> float:
        self.zoom_level = round(max(1.0, min(5.0, self.zoom_level + delta)), 2)
        return self.zoom_level

    def step_dwell_watchdog(self, pixel_delta: float, dt_seconds: float) -> DualCaptureSnapshot | None:
        """Track frame-to-frame pixel delta; auto-snap when still for 1.5s after motion spike."""
        if pixel_delta >= DWELL_MOTION_SPIKE_THRESHOLD:
            self.motion_spiked = True
            self.dwell_timer_s = 0.0
            return None

        if self.motion_spiked and pixel_delta <= DWELL_STILLNESS_THRESHOLD:
            self.dwell_timer_s += dt_seconds
            if self.dwell_timer_s >= DWELL_TO_INSPECT_SECONDS:
                self.motion_spiked = False
                self.dwell_timer_s = 0.0
                return self.capture_synchronized_dual_frame(trigger_source="DWELL_WATCHDOG")
        return None

    def capture_synchronized_dual_frame(
        self, trigger_source: str = "F14_FOOT_PEDAL"
    ) -> DualCaptureSnapshot:
        """Grab simultaneous frames from Overhead Cam 0 + Macro Cam 1."""
        RAW_CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
        now = time.time()
        snap = DualCaptureSnapshot(
            timestamp=now,
            overhead_cam_id=self.overhead_cam_id,
            macro_cam_id=self.macro_cam_id,
            zoom_level=self.zoom_level,
            trigger_source=trigger_source,
            dwell_locked=(trigger_source == "DWELL_WATCHDOG"),
            summary=(
                f"Synchronized Dual-Cam Snapshot [{trigger_source}] | "
                f"Cam 0 (Overhead Wide) + Cam 1 (Macro {self.zoom_level:.1f}x)"
            ),
        )
        self.snapshots.append(snap)
        return snap
