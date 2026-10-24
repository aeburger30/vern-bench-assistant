"""Dual-Microphone Router (RØDE Wireless GO III USB-C priority + Shotgun mic failover)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

try:
    import sounddevice as sd
except Exception:
    sd = None  # type: ignore[assignment]


@dataclass
class AudioRouteStatus:
    active_badge: str = "[MIC: RØDE TX1]"
    active_source: str = "RØDE TX1"
    stereo_split_enabled: bool = True
    tx1_rms_db: float = -18.0
    tx2_probe_rms_db: float = -42.0
    device_name: str = "Simulated RØDE Wireless GO III (USB-C)"


class DualMicRouter:
    """Routes Technician Voice (Left/TX1) & Acoustic Probe (Right/TX2) with Shotgun failover."""

    def __init__(self, rms_failover_threshold_db: float = -55.0) -> None:
        self.rms_failover_threshold_db = rms_failover_threshold_db
        self._rode_active = True
        self._phase = 0.0

    def enumerate_inputs(self) -> list[dict[str, Any]]:
        if sd is None:
            return []
        try:
            devices = sd.query_devices()
            return [
                {"index": idx, "name": d.get("name", ""), "channels": d.get("max_input_channels", 0)}
                for idx, d in enumerate(devices)
                if d.get("max_input_channels", 0) > 0
            ]
        except Exception:
            return []

    def toggle_mic_source(self) -> str:
        """Toggle between RØDE Wireless GO III (TX1) and VS-20501 Shotgun Mic for testing failover."""
        self._rode_active = not self._rode_active
        return "RØDE TX1" if self._rode_active else "SHOTGUN"

    def get_status(self) -> AudioRouteStatus:
        if self._rode_active:
            return AudioRouteStatus(
                active_badge="[MIC: RØDE TX1]",
                active_source="RØDE TX1",
                stereo_split_enabled=True,
                tx1_rms_db=-16.5,
                tx2_probe_rms_db=-38.0,
                device_name="RØDE Wireless GO III (USB-C)",
            )
        return AudioRouteStatus(
            active_badge="[MIC: SHOTGUN]",
            active_source="SHOTGUN",
            stereo_split_enabled=False,
            tx1_rms_db=-21.0,
            tx2_probe_rms_db=-60.0,
            device_name="VS-20501 Chassis Shotgun Mic",
        )

    def sample_waveform_points(self, num_points: int = 64, speaking: bool = False) -> list[float]:
        """Generate normalized [-1.0, 1.0] oscilloscope phosphor waveform samples."""
        self._phase += 0.35
        amp = 0.78 if speaking else (0.38 if self._rode_active else 0.22)
        points: list[float] = []
        for i in range(num_points):
            t = (i / max(1, num_points - 1)) * math.pi * 4.0 + self._phase
            carrier = math.sin(t) * 0.65 + math.sin(t * 2.3 - self._phase * 0.5) * 0.35
            envelope = math.sin((i / max(1, num_points - 1)) * math.pi)
            points.append(max(-1.0, min(1.0, carrier * envelope * amp)))
        return points
