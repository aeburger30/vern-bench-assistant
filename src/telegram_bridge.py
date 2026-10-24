"""Telegram Mobile Probe for roving smartphone photos ('wireless facsimile from your pocket radiotelephone')."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import (
    ANACHRONISM_DICTIONARY,
    TELEGRAM_BOARD_TILE_SIZE,
    TELEGRAM_COMPONENT_CROP_SIZE,
)


@dataclass
class TelegramProbePayload:
    mode: str  # "single_component" or "full_board"
    target_resolution: tuple[int, int]
    estimated_tokens: int
    anachronism_label: str


def plan_telegram_image_prep(inquiry_type: str = "single_component") -> TelegramProbePayload:
    """Return resolution and token budget for smartphone probe photos per SPEC Section 7."""
    if inquiry_type.strip().lower() == "single_component":
        return TelegramProbePayload(
            mode="single_component",
            target_resolution=TELEGRAM_COMPONENT_CROP_SIZE,
            estimated_tokens=258,
            anachronism_label=ANACHRONISM_DICTIONARY["telegram_photo"],
        )
    return TelegramProbePayload(
        mode="full_board",
        target_resolution=TELEGRAM_BOARD_TILE_SIZE,
        estimated_tokens=768,
        anachronism_label=ANACHRONISM_DICTIONARY["telegram_photo"],
    )
