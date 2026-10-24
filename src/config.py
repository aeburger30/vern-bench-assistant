"""Configuration, environment variables, and hardware/model constants for V.E.R.N."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Project Root & Standard Directories
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR: Path = PROJECT_ROOT / "knowledge"
DOCS_RESTORATIONS_DIR: Path = PROJECT_ROOT / "docs" / "restorations"
RAW_CAPTURES_DIR: Path = PROJECT_ROOT / "raw_captures"

# Knowledge Base File Paths
TRANSISTOR_RULES_PATH: Path = KNOWLEDGE_DIR / "transistor_rules.json"
CAPACITOR_TABLE_PATH: Path = KNOWLEDGE_DIR / "capacitor_table.json"
AUDIO_VOCABULARY_PATH: Path = KNOWLEDGE_DIR / "audio_vocabulary.json"
MODEL_QUIRKS_PATH: Path = KNOWLEDGE_DIR / "model_quirks.md"

# Environment Variables
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
GDRIVE_MANUALS_DIR: Path = Path(
    os.getenv("GDRIVE_MANUALS_DIR", str(Path.home() / "Google Drive" / "Vintage_Audio_Manuals"))
)
WORKBENCH_DB_PATH: Path = Path(
    os.getenv("WORKBENCH_DB_PATH", str(PROJECT_ROOT / "workbench.db"))
)
GITHUB_AUTO_PUSH: bool = os.getenv("GITHUB_AUTO_PUSH", "false").lower() in ("1", "true", "yes")

# Cloud & Gemini API Routing Constants (Section 4)
ROUTINE_MODEL: str = os.getenv("VERN_ROUTINE_MODEL", "gemini-2.5-flash")
DEEP_SCHEMATIC_MODEL: str = os.getenv("VERN_DEEP_MODEL", "gemini-2.5-pro")
FILES_API_TTL_HOURS: float = 47.5
FILES_API_TTL_SECONDS: float = FILES_API_TTL_HOURS * 3600.0
CONTEXT_CACHE_TTL_SECONDS: int = 3600
CONTEXT_CACHE_MIN_TOKENS: int = 2048

# 8.5-Inch 4:3 Retro HUD & Physical Enclosure Constants (Sections 1 & 8)
HUD_WIDTH: int = 1024
HUD_HEIGHT: int = 768
HUD_ASPECT_RATIO: str = "4:3"
PHOSPHOR_GREEN: str = "#00FF66"
PITCH_BLACK: str = "#000000"

SCREW_BIN_LABELS: tuple[str, str, str] = ("Bin A", "Bin B", "Bin C")
VALID_TRAY_STATES: tuple[str, str] = ("EXTENDED", "RETRACTED")
VALID_BEACON_COLORS: tuple[str, str, str] = ("GREEN", "AMBER", "RED")

# Vision & Audio Constants (Section 7)
DWELL_TO_INSPECT_SECONDS: float = 1.5
DWELL_MOTION_SPIKE_THRESHOLD: float = 12.0
DWELL_STILLNESS_THRESHOLD: float = 2.0
TELEGRAM_COMPONENT_CROP_SIZE: tuple[int, int] = (384, 384)
TELEGRAM_BOARD_TILE_SIZE: tuple[int, int] = (768, 768)

# 1981 Anachronism Dictionary (Section 2)
ANACHRONISM_DICTIONARY: dict[str, str] = {
    "internet": "the global bulletin board system (BBS) / the World Wide Web",
    "audiokarma": "the global bulletin board system (BBS)",
    "smartphone_photo": "wireless facsimile from your pocket radiotelephone",
    "telegram_photo": "wireless facsimile from your pocket radiotelephone",
    "sqlite_db": "my solid-state memory banks",
    "github_repo": "the off-site magnetic tape vault",
    "git_commit": "punching a permanent revision card",
    "overhead_camera": "the overhead vidicon tube",
    "macro_camera": "the high-magnification optical scanner",
    "rode_mic": "your FM lapel telemetry pack",
    "distributor_api": "the computerized mail-order catalog",
}
