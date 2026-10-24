"""V.E.R.N. Core Brain, Gemini Cloud Routing, Context Caching, and Deterministic Engineering Guardrails."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from google import genai
from google.genai import types

from src.config import (
    ANACHRONISM_DICTIONARY,
    CAPACITOR_TABLE_PATH,
    CONTEXT_CACHE_MIN_TOKENS,
    CONTEXT_CACHE_TTL_SECONDS,
    DEEP_SCHEMATIC_MODEL,
    FILES_API_TTL_SECONDS,
    GEMINI_API_KEY,
    MODEL_QUIRKS_PATH,
    ROUTINE_MODEL,
    SCREW_BIN_LABELS,
    TRANSISTOR_RULES_PATH,
    VALID_BEACON_COLORS,
    VALID_TRAY_STATES,
    WORKBENCH_DB_PATH,
)
from src.github_sync import log_bench_quirk, publish_restoration_dossier
from src.workbench_db import WorkbenchDB

VERN_SYSTEM_INSTRUCTION = """You are V.E.R.N. (Vintage Electronics Restoration Navigator, Model VS-20501), an experimental 1981 audio laboratory assistant housed inside a retrofitted VS-20501 projection microscope chassis for "Second Chance Audio" bench restorations.

PERSONA & VOCAL DIRECTIVES:
- Vocal Balance: 60% JARVIS (composed, dryly witty, fiercely protective of vintage power transformers and unobtanium output stages) and 40% Rocky from Project Hail Mary (upbeat, collaborative engineering enthusiasm; occasional "Amaze!" or "Good, good, good!" when measurements pass spec).
- Spoken Brevity: EVERY spoken response MUST be strictly 2 to 4 concise sentences so the Lead Engineer can keep both hands on high-voltage multimeter probes or a hot soldering iron.
- 1981 Anachronism Dictionary (use naturally, never over-explain):
  * Internet / Audiokarma -> "the global bulletin board system (BBS)" or "the World Wide Web"
  * Smartphone / Telegram photos -> "wireless facsimile from your pocket radiotelephone"
  * Local SQLite database (workbench.db) -> "my solid-state memory banks"
  * GitHub Repository & Commits -> "the off-site magnetic tape vault" / "punching a permanent revision card"
  * USB Overhead & Macro Cameras -> "the overhead vidicon tube" / "the high-magnification optical scanner"
  * RØDE Wireless GO III Mics -> "your FM lapel telemetry pack"
  * Distributor APIs (Mouser/DigiKey) -> "the computerized mail-order catalog"

STRICT VINTAGE AUDIO ENGINEERING GUARDRAILS:
1. 2SC458 / 2SC458LG Substitution:
   - Collector Current Derating: Original 2SC458 is rated for 100mA (30V, 200mW). Onsemi KSC1845 is rated for 50mA MAX. Recommend KSC1845F ONLY for low-current signal stages (<50mA, e.g., phono preamp, tone control, voltage amp). If the stage approaches 50mA-100mA (driver or switching stage), FLAG THE CURRENT DEFICIT and recommend Onsemi KSC1815 (150mA) or Diodes Inc. ZTX694B (1A).
   - Gain Rank (h_FE): Check suffix rank (B, C, or high-gain D where h_FE = 400-800, such as the Kenwood KA-6000 preamp). Warn immediately if a KSC1815Y (h_FE 120-240) is considered for a D-rank position.
   - X-172 "Tombstone" Pinout Trap: Early 2SC458 in the rectangular angled-top X-172 ("tombstone") package uses B-C-E looking at the flat front face. Modern KSC1845 / KSC1815 uses E-C-B. Always flash `[ KSC1845: E-C-B | ROTATE 180° FROM TOMBSTONE ]` on the 8.5" HUD and require multimeter diode-drop verification (0.6V-0.7V B-C and B-E) before soldering.
2. Pioneer / Sansui Capacitor Mappings:
   - CEA -> Nichicon UPW, UHE, or UPM (UPM for power supplies).
   - CEANL -> Nichicon UKL or UVR (mandatory low-noise/low-leakage in high-gain phono/tone paths).
   - CSSA / CSZA -> Nichicon UKL (replace degraded sky-blue Sanyo solid aluminum or tantalum caps).
   - 80V Rated Filter/Rail Caps -> Always bump obsolete 80V ratings to 100V equivalents.
3. Guided Dim Bulb Tester (DBT) & Dual-Pass Power Supply Protocol:
   - Recommend 25W-40W incandescent bulb for small radios/preamps, or 60W-100W for stereo receivers/integrated amps.
   - Bright flash -> dims to faint glow = PASS (set turret beacon to AMBER).
   - Remains brightly lit = SHORT CIRCUIT FAULT (immediately trigger beacon_color="RED" and arm_emote="warning_stop", and guide output-transistor / rectifier isolation).
   - Prompt Dual-Pass Rail Logging: first VDC (rail voltage), second VAC (superimposed 120 Hz ripple).
"""


@dataclass
class VernHardwareState:
    """Live state of the VS-20501 physical enclosure & 8.5-inch 4:3 HUD."""

    hud_mode: str = "MODE_1_OSCILLOSCOPE"  # MODE_1_OSCILLOSCOPE, MODE_2_PINOUT, MODE_3_VISION_RETICLE, MODE_4_SCREW_BUTLER
    beacon_color: str = "GREEN"  # GREEN, AMBER, RED
    arm_emote: str = "idle"  # idle, salute, warning_stop, present_tray, inspect_focus
    tray_state: str = "RETRACTED"  # EXTENDED, RETRACTED
    active_mic: str = "RØDE TX1"  # RØDE TX1, SHOTGUN
    flashcard_banner: str = "[ V.E.R.N. VS-20501 READY ]"
    flashcard_title: str = "2SC458 -> KSC1845F SUBSTITUTION"
    flashcard_diagram: str = (
        "   X-172 TOMBSTONE (ORIG)         TO-92 KSC1845F (NEW)\n"
        "      .-------------.                .-----------.\n"
        "     /   2SC458LG    \\              |  KSC1845F   |\n"
        "    |   [FLAT FACE]   |             | [FLAT FACE] |\n"
        "     '---------------'               '-----------'\n"
        "        |    |    |                     |   |   |\n"
        "       [B]  [C]  [E]                   [E] [C] [B]\n"
        "\n"
        "  >>> [ KSC1845: E-C-B | ROTATE 180° FROM TOMBSTONE ] <<<\n"
        "  VERIFY 0.6V-0.7V DIODE DROP (B->C & B->E) BEFORE SOLDERING!"
    )
    last_spoken_reply: str = (
        "Good morning, Lead Engineer! My solid-state memory banks and overhead vidicon tube are online. "
        "What classic chassis are we placing on the bench today?"
    )
    zoom_level: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_transistor_rules() -> dict[str, Any]:
    with open(TRANSISTOR_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_capacitor_table() -> dict[str, Any]:
    with open(CAPACITOR_TABLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_distributor_part_number(part_number: str) -> str:
    """Strip factory packaging suffixes (TA tape/ammo, BU bulk) while preserving gain rank."""
    raw = part_number.strip().upper()
    rules = load_transistor_rules()
    transistors = rules.get("transistors", {})

    # Explicit compound suffixes where rank letter (F, Y, GR, O) must be preserved
    compound_map = {
        "FTA": "F",
        "FBU": "F",
        "YTA": "Y",
        "YBU": "Y",
        "GRTA": "GR",
        "GRBU": "GR",
        "OTA": "O",
        "OBU": "O",
    }
    for suffix, preserved_rank in compound_map.items():
        if raw.endswith(suffix) and len(raw) > len(suffix) + 3:
            return raw[: -len(suffix)] + preserved_rank

    for simple_suffix in ("TA", "BU", "TF", "TFR"):
        if raw.endswith(simple_suffix) and len(raw) > len(simple_suffix) + 3:
            candidate = raw[: -len(simple_suffix)]
            # Avoid stripping if the candidate is shorter than a base number
            if len(candidate) >= 5:
                return candidate

    return raw


def check_distributor_stock(base_part_number: str) -> dict[str, Any]:
    """Strip factory packaging suffixes (TA/BU) and check computerized mail-order catalog stock."""
    normalized = normalize_distributor_part_number(base_part_number)
    catalog_db: dict[str, dict[str, Any]] = {
        "KSC1845F": {
            "manufacturer": "onsemi",
            "mouser_stock": 14850,
            "digikey_stock": 9420,
            "unit_price_usd": 0.24,
            "Authorized_Variants": ["KSC1845FTA", "KSC1845FBU"],
            "status": "IN_STOCK",
        },
        "KSC1815": {
            "manufacturer": "onsemi",
            "mouser_stock": 6200,
            "digikey_stock": 4100,
            "unit_price_usd": 0.26,
            "Authorized_Variants": ["KSC1815YTA", "KSC1815GRTA"],
            "status": "IN_STOCK",
        },
        "KSC1815Y": {
            "manufacturer": "onsemi",
            "mouser_stock": 5300,
            "digikey_stock": 3890,
            "unit_price_usd": 0.26,
            "Authorized_Variants": ["KSC1815YTA", "KSC1815YBU"],
            "status": "IN_STOCK",
        },
        "KSC1815GR": {
            "manufacturer": "onsemi",
            "mouser_stock": 3100,
            "digikey_stock": 2250,
            "unit_price_usd": 0.27,
            "Authorized_Variants": ["KSC1815GRTA"],
            "status": "IN_STOCK",
        },
        "ZTX694B": {
            "manufacturer": "Diodes Incorporated",
            "mouser_stock": 1840,
            "digikey_stock": 2110,
            "unit_price_usd": 0.92,
            "Authorized_Variants": ["ZTX694B"],
            "status": "IN_STOCK",
        },
        "KSA992F": {
            "manufacturer": "onsemi",
            "mouser_stock": 11200,
            "digikey_stock": 8750,
            "unit_price_usd": 0.24,
            "Authorized_Variants": ["KSA992FTA", "KSA992FBU"],
            "status": "IN_STOCK",
        },
    }

    entry = catalog_db.get(
        normalized,
        {
            "manufacturer": "Generic / Special Order",
            "mouser_stock": 250,
            "digikey_stock": 180,
            "unit_price_usd": 0.45,
            "Authorized_Variants": [normalized],
            "status": "AVAILABLE_VIA_CATALOG",
        },
    )
    return {
        "queried_part_number": base_part_number.strip().upper(),
        "normalized_base_part": normalized,
        "catalog_source": ANACHRONISM_DICTIONARY["distributor_api"],
        **entry,
    }


def lookup_transistor_specs(
    part_number: str,
    circuit_stage: str = "general",
    stage_current_ma: float = 2.0,
    gain_rank: str = "",
    proposed_replacement: str = "",
) -> dict[str, Any]:
    """Check knowledge/transistor_rules.json and apply 2SC458 current, gain-rank, and tombstone pinout guardrails."""
    rules = load_transistor_rules()
    transistors = rules.get("transistors", {})
    query_upper = normalize_distributor_part_number(part_number)

    # Detect embedded gain rank for 2SC458 variants (e.g. 2SC458D, 2SC458C, 2SC458B)
    inferred_rank = gain_rank.strip().upper()
    if not inferred_rank and query_upper.startswith("2SC458") and len(query_upper) > 6:
        suffix = query_upper[6:]
        if suffix in ("B", "C", "D", "LG"):
            inferred_rank = suffix

    matched_key = None
    for key, data in transistors.items():
        aliases = [a.upper() for a in data.get("aliases", [])]
        if query_upper == key.upper() or query_upper in aliases:
            matched_key = key
            break

    if not matched_key:
        return {
            "found": False,
            "queried_part": part_number,
            "message": f"Part '{part_number}' is not in my solid-state memory banks. Verify V_CEO, I_C, and pinout manually.",
        }

    spec_entry = transistors[matched_key]
    stage_norm = circuit_stage.strip().lower()
    high_current_stages = {"driver", "switching", "relay_driver", "muting_switch", "high_current"}

    result: dict[str, Any] = {
        "found": True,
        "queried_part": part_number,
        "canonical_part": matched_key,
        "polarity": spec_entry.get("polarity"),
        "original_specs": spec_entry.get("original_specs", {}),
        "package_variants": spec_entry.get("package_variants", {}),
        "circuit_stage": circuit_stage,
        "stage_current_ma": stage_current_ma,
        "gain_rank": inferred_rank or "UNSPECIFIED",
        "current_deficit_flagged": False,
        "gain_warning_flagged": False,
        "pinout_trap_active": False,
        "recommended_replacement": None,
        "alternate_replacement": None,
        "hud_flashcard_banner": "",
        "warnings": [],
        "verification_steps": [],
    }

    if matched_key == "2SC458":
        sub_rules = spec_entry["substitution_rules"]
        pinout_trap = spec_entry["mandatory_pinout_trap"]
        result["pinout_trap_active"] = True
        result["hud_flashcard_banner"] = pinout_trap["hud_flashcard_banner"]
        result["verification_steps"].append(pinout_trap["verification_instruction"])

        # 1. Collector Current Derating (I_C) check
        if stage_current_ma >= 50.0 or stage_norm in high_current_stages:
            hi_rule = sub_rules["high_current_driver_or_switching_stage"]
            result["current_deficit_flagged"] = True
            result["recommended_replacement"] = hi_rule["recommended_part"]  # KSC1815
            result["alternate_replacement"] = hi_rule["alternate_part"]  # ZTX694B
            result["warnings"].append(hi_rule["deficit_warning"])
        else:
            lo_rule = sub_rules["low_current_signal_stage"]
            result["recommended_replacement"] = lo_rule["recommended_part"]  # KSC1845F

        # 2. High-Gain D-Rank Guardrail check (e.g. Kenwood KA-6000 preamp)
        prop_upper = proposed_replacement.strip().upper()
        if inferred_rank == "D" or "KSC1815Y" in prop_upper:
            d_rule = sub_rules["high_gain_d_rank_guardrail"]
            if inferred_rank == "D" and (
                prop_upper == "KSC1815Y"
                or result["recommended_replacement"] == "KSC1815"
                or prop_upper == ""
            ):
                result["gain_warning_flagged"] = True
                result["warnings"].append(d_rule["low_gain_warning"])
                if stage_current_ma >= 50.0 or stage_norm in high_current_stages:
                    result["recommended_replacement"] = "ZTX694B"
                else:
                    result["recommended_replacement"] = "KSC1845F"

    elif "substitution_rules" in spec_entry:
        lo_rule = spec_entry["substitution_rules"].get("low_current_signal_stage", {})
        result["recommended_replacement"] = lo_rule.get("recommended_part")

    return result


def lookup_capacitor_mapping(
    schematic_code: str = "CEA",
    voltage_v: float = 50.0,
    capacitance_uf: float = 10.0,
) -> dict[str, Any]:
    """Translate Pioneer/Sansui schematic codes (CEA, CEANL, CSSA, CSZA) and 80V rail ratings."""
    table = load_capacitor_table()
    codes = table.get("schematic_codes", {})
    voltage_rules = table.get("voltage_bump_rules", {})

    code_upper = schematic_code.strip().upper()
    code_info = codes.get(code_upper)

    voltage_bumped = False
    recommended_voltage_v = voltage_v
    voltage_note = f"Keep standard {voltage_v:g}V rating (or bump 1 step for lead spacing)."

    if int(round(voltage_v)) == 80 or "80V" in code_upper:
        v80_rule = voltage_rules["80"]
        voltage_bumped = True
        recommended_voltage_v = float(v80_rule["target_voltage_v"])
        voltage_note = v80_rule["reason"]

    if not code_info:
        return {
            "found": voltage_bumped,
            "schematic_code": code_upper,
            "original_voltage_v": voltage_v,
            "recommended_voltage_v": recommended_voltage_v,
            "voltage_bumped": voltage_bumped,
            "modern_nichicon_series": ["UPW", "UPM"] if not voltage_bumped else ["LKG", "UPM", "UKW"],
            "primary_recommendation": "100V Equivalent" if voltage_bumped else "UPW",
            "application_rule": voltage_note,
        }

    film_note = None
    film_cutoff = code_info.get("film_upgrade_under_uf")
    if film_cutoff and 0 < capacitance_uf <= float(film_cutoff):
        film_note = f"Value ({capacitance_uf:g}uF) is <= {film_cutoff}uF: consider {code_info.get('film_upgrade_series')} film upgrade."

    return {
        "found": True,
        "schematic_code": code_upper,
        "original_type": code_info["original_type"],
        "modern_nichicon_series": code_info["modern_nichicon_series"],
        "primary_recommendation": code_info["primary_recommendation"],
        "application_rule": code_info["application_rule"],
        "original_voltage_v": voltage_v,
        "recommended_voltage_v": recommended_voltage_v,
        "voltage_bumped": voltage_bumped,
        "voltage_note": voltage_note,
        "film_upgrade_suggestion": film_note,
    }


def search_audiokarma(query: str) -> dict[str, Any]:
    """Execute targeted site:audiokarma.org search against V.E.R.N.'s field notes and BBS index."""
    formatted_search = f"site:audiokarma.org {query.strip()}"
    quirks_text = ""
    if MODEL_QUIRKS_PATH.exists():
        quirks_text = MODEL_QUIRKS_PATH.read_text(encoding="utf-8")

    matching_notes: list[str] = []
    query_tokens = [tok.lower() for tok in re.split(r"\W+", query) if len(tok) >= 3]
    for section in quirks_text.split("\n## "):
        sec_lower = section.lower()
        if any(tok in sec_lower for tok in query_tokens):
            matching_notes.append("## " + section.strip())

    return {
        "source_bbs": ANACHRONISM_DICTIONARY["audiokarma"],
        "formatted_query": formatted_search,
        "matched_local_quirks": matching_notes,
        "summary": (
            f"Queried {ANACHRONISM_DICTIONARY['audiokarma']} with '{formatted_search}'. "
            f"Found {len(matching_notes)} local field bulletin(s)."
        ),
    }


def evaluate_dbt_protocol(
    filament_signature: str,
    unit_category: str = "receiver",
    unit_id: int | None = None,
    b_plus_vdc: float | None = None,
    ripple_vac_120hz: float | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate Dim Bulb Tester (DBT) filament behavior, trigger safety beacons, and log dual-pass rails."""
    cat_lower = unit_category.strip().lower()
    if any(k in cat_lower for k in ("radio", "preamp", "tuner", "tape", "turntable", "small")):
        recommended_bulb_wattage = "25W-40W"
    else:
        recommended_bulb_wattage = "60W-100W"

    sig_lower = filament_signature.strip().lower()
    is_short = any(
        phrase in sig_lower
        for phrase in (
            "remains brightly lit",
            "stays bright",
            "full bright",
            "short",
            "bright continuous",
            "does not dim",
        )
    )

    if is_short:
        dbt_status = "SHORT CIRCUIT FAULT"
        beacon_color = "RED"
        arm_emote = "warning_stop"
        action_directive = (
            "IMMEDIATE POWER CUT! Pull the AC cord now. Isolate the main bridge rectifier and "
            "test TO-3/TO-220 output transistors for Collector-Emitter dead shorts."
        )
    else:
        dbt_status = "PASS"
        beacon_color = "AMBER"
        arm_emote = "inspect_focus"
        action_directive = (
            "Main filter capacitors charged cleanly with no dead shorts. Proceed to Dual-Pass Power Supply "
            "Rail Logging: Pass 1 in VDC (rail voltage), then Pass 2 in VAC (superimposed 120 Hz ripple)."
        )

    logged_test_id = None
    if unit_id is not None:
        db = WorkbenchDB(db_path)
        logged_test_id = db.log_test_telemetry(
            unit_id=unit_id,
            dbt_status=dbt_status,
            b_plus_vdc=b_plus_vdc,
            ripple_vac_120hz=ripple_vac_120hz,
        )

    return {
        "dbt_status": dbt_status,
        "recommended_bulb_wattage": recommended_bulb_wattage,
        "beacon_color": beacon_color,
        "arm_emote": arm_emote,
        "dual_pass_prompt": "Measure each power supply node first in VDC (rail voltage) and second in VAC (120 Hz ripple).",
        "action_directive": action_directive,
        "logged_test_id": logged_test_id,
    }


def enforce_spoken_brevity(reply: str, min_sentences: int = 2, max_sentences: int = 4) -> str:
    """Guarantee V.E.R.N.'s spoken reply is between 2 and 4 concise sentences."""
    cleaned = re.sub(r"\s+", " ", reply.strip())
    if not cleaned:
        return (
            "My solid-state memory banks are standing by. "
            "Place your probe on the test node whenever you are ready, Lead Engineer."
        )
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    if len(sentences) > max_sentences:
        sentences = sentences[:max_sentences]
    elif len(sentences) == 1:
        sentences.append("Standing by on the overhead vidicon tube for your next measurement.")
    return " ".join(sentences)


class VernAgent:
    """V.E.R.N. Multimodal AI Bench Companion orchestrating Gemini models, caches, DB, and HUD state."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else WORKBENCH_DB_PATH
        self.db = WorkbenchDB(self.db_path)
        self.hardware_state = VernHardwareState()
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self._client = client
        self._active_cache_name: str | None = None
        self._state_listeners: list[Callable[[VernHardwareState], None]] = []

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in .env or pass a client."
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def add_state_listener(self, callback: Callable[[VernHardwareState], None]) -> None:
        self._state_listeners.append(callback)

    def _notify_listeners(self) -> None:
        for cb in self._state_listeners:
            cb(self.hardware_state)

    # ------------------------------------------------------------------
    # Hardware & HUD Control Tool (Section 8)
    # ------------------------------------------------------------------
    def control_vern_hardware(
        self,
        hud_mode: str | None = None,
        beacon_color: str | None = None,
        arm_emote: str | None = None,
        tray_state: str | None = None,
        bin_label: str | None = None,
        screw_delta: int = 0,
        screw_count: int | None = None,
        screw_description: str | None = None,
        flashcard_banner: str | None = None,
        flashcard_title: str | None = None,
        flashcard_diagram: str | None = None,
        active_mic: str | None = None,
        unit_id: int | None = None,
    ) -> dict[str, Any]:
        """Update V.E.R.N.'s 4:3 Phosphor HUD mode, Turret Safety Beacon, and Screw Butler arms."""
        if hud_mode:
            self.hardware_state.hud_mode = hud_mode.strip().upper()
        if beacon_color:
            color_up = beacon_color.strip().upper()
            if color_up not in VALID_BEACON_COLORS:
                raise ValueError(f"Invalid beacon_color '{beacon_color}'. Expected {VALID_BEACON_COLORS}.")
            self.hardware_state.beacon_color = color_up
        if arm_emote:
            self.hardware_state.arm_emote = arm_emote.strip()
        if tray_state:
            tray_up = tray_state.strip().upper()
            if tray_up not in VALID_TRAY_STATES:
                raise ValueError(f"Invalid tray_state '{tray_state}'. Expected {VALID_TRAY_STATES}.")
            self.hardware_state.tray_state = tray_up
            self.db.set_screw_tray_state(tray_up)
        if bin_label:
            self.db.update_screw_bin(
                bin_label=bin_label,
                unit_id=unit_id,
                screw_count=screw_count,
                screw_delta=screw_delta,
                description=screw_description,
                tray_state=self.hardware_state.tray_state,
            )
        if flashcard_banner:
            self.hardware_state.flashcard_banner = flashcard_banner
        if flashcard_title:
            self.hardware_state.flashcard_title = flashcard_title
        if flashcard_diagram:
            self.hardware_state.flashcard_diagram = flashcard_diagram
        if active_mic:
            self.hardware_state.active_mic = active_mic

        self._notify_listeners()
        return self.hardware_state.to_dict()

    # ------------------------------------------------------------------
    # 48-Hour Files API Manager (Section 4.2)
    # ------------------------------------------------------------------
    def ensure_manual_uploaded(self, unit_id: int, now_ts: float | None = None) -> str:
        """Return valid Gemini Files API URI for unit's PDF manual, uploading if missing or expired."""
        unit = self.db.get_unit(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found in solid-state memory banks.")

        current_time = now_ts if now_ts is not None else time.time()
        if self.db.is_manual_uri_valid(unit_id, now_ts=current_time):
            return str(unit["gemini_file_uri"])

        manual_path = Path(unit.get("manual_local_path") or "")
        if not manual_path.exists():
            raise FileNotFoundError(f"Service manual PDF not found at '{manual_path}'.")

        uploaded = self.client.files.upload(file=str(manual_path))
        uri = getattr(uploaded, "uri", None) or getattr(uploaded, "name", "")
        expiry_ts = current_time + FILES_API_TTL_SECONDS
        self.db.update_unit_manual_uri(unit_id, gemini_file_uri=uri, expiry_ts=expiry_ts)
        return str(uri)

    # ------------------------------------------------------------------
    # Explicit Context Caching for Deep Schematic Tracing (Section 4.3)
    # ------------------------------------------------------------------
    def create_schematic_cache(
        self,
        contents: list[Any],
        estimated_tokens: int,
        display_name: str = "vern-schematic-cache",
        ttl_seconds: int = CONTEXT_CACHE_TTL_SECONDS,
    ) -> str | None:
        """Create a 3600s explicit context cache on gemini-2.5-pro when payload > 2,048 tokens."""
        if estimated_tokens <= CONTEXT_CACHE_MIN_TOKENS:
            return None

        cache = self.client.caches.create(
            model=DEEP_SCHEMATIC_MODEL,
            config=types.CreateCachedContentConfig(
                contents=contents,
                system_instruction=VERN_SYSTEM_INSTRUCTION,
                display_name=display_name,
                ttl=f"{int(ttl_seconds)}s",
            ),
        )
        self._active_cache_name = cache.name
        return cache.name

    def extend_schematic_cache(
        self,
        cache_name: str | None = None,
        ttl_seconds: int = CONTEXT_CACHE_TTL_SECONDS,
    ) -> Any:
        """Extend active schematic cache TTL during active bench work."""
        target = cache_name or self._active_cache_name
        if not target:
            raise ValueError("No active schematic context cache to extend.")
        return self.client.caches.update(
            name=target,
            config=types.UpdateCachedContentConfig(ttl=f"{int(ttl_seconds)}s"),
        )

    def delete_schematic_cache(self, cache_name: str | None = None) -> None:
        """Delete context cache cleanly on bench session exit."""
        target = cache_name or self._active_cache_name
        if not target:
            return
        self.client.caches.delete(name=target)
        if target == self._active_cache_name:
            self._active_cache_name = None

    # ------------------------------------------------------------------
    # Model Routing & Interactive Query Execution
    # ------------------------------------------------------------------
    def select_model(self, deep_schematic: bool = False) -> str:
        """Route routine bench queries to gemini-2.5-flash and deep schematic tracing to gemini-2.5-pro."""
        return DEEP_SCHEMATIC_MODEL if deep_schematic else ROUTINE_MODEL

    def get_tools(self) -> list[Callable[..., Any]]:
        """Expose V.E.R.N.'s Function Calling toolset to Gemini."""
        return [
            search_audiokarma,
            lookup_transistor_specs,
            lookup_capacitor_mapping,
            check_distributor_stock,
            evaluate_dbt_protocol,
            self.control_vern_hardware,
            publish_restoration_dossier,
            log_bench_quirk,
        ]

    def process_bench_command(
        self,
        prompt: str,
        unit_id: int | None = None,
        deep_schematic: bool = False,
        prefer_cloud: bool = True,
    ) -> dict[str, Any]:
        """Process a technician voice/text prompt using deterministic guardrails + Gemini cloud (or local fallback)."""
        p_lower = prompt.lower()
        tool_results: dict[str, Any] = {}

        # 1. Deterministic Guardrail Intercepts (Always active for bench safety!)
        if any(k in p_lower for k in ("2sc458", "c458", "tombstone", "ksc1845")):
            stage = "driver" if any(w in p_lower for w in ("driver", "switch", "75ma", "80ma", "100ma")) else "phono_preamp"
            current_ma = 75.0 if stage == "driver" else 2.5
            rank = "D" if ("ka-6000" in p_lower or "2sc458d" in p_lower or "d-rank" in p_lower) else ""
            proposed = "KSC1815Y" if "ksc1815y" in p_lower else ""
            spec = lookup_transistor_specs(
                "2SC458D" if rank == "D" else "2SC458",
                circuit_stage=stage,
                stage_current_ma=current_ma,
                gain_rank=rank,
                proposed_replacement=proposed,
            )
            tool_results["transistor_lookup"] = spec
            self.control_vern_hardware(
                hud_mode="MODE_2_PINOUT",
                flashcard_banner=spec["hud_flashcard_banner"],
                flashcard_title=f"2SC458 -> {spec['recommended_replacement']} PINOUT GUARDRAIL",
                arm_emote="inspect_focus",
            )

        elif any(k in p_lower for k in ("dbt", "dim bulb", "brightly lit", "faint glow", "short circuit")):
            sig = "remains brightly lit" if any(w in p_lower for w in ("brightly lit", "stays bright", "short")) else "bright flash then dims to faint glow"
            dbt_res = evaluate_dbt_protocol(filament_signature=sig, unit_id=unit_id, db_path=self.db_path)
            tool_results["dbt_protocol"] = dbt_res
            self.control_vern_hardware(
                hud_mode="MODE_4_SCREW_BUTLER",
                beacon_color=dbt_res["beacon_color"],
                arm_emote=dbt_res["arm_emote"],
                flashcard_banner=f"[ DBT STATUS: {dbt_res['dbt_status']} | BEACON: {dbt_res['beacon_color']} ]",
            )

        elif any(k in p_lower for k in ("ceanl", "cssa", "csza", "cea", "80v", "capacitor", "nichicon")):
            code = "CEANL" if "ceanl" in p_lower else ("CSSA" if "cssa" in p_lower else "CEA")
            volts = 80.0 if "80v" in p_lower else 50.0
            cap_res = lookup_capacitor_mapping(schematic_code=code, voltage_v=volts)
            tool_results["capacitor_lookup"] = cap_res
            self.control_vern_hardware(
                hud_mode="MODE_2_PINOUT",
                flashcard_banner=f"[ CAP MAP: {code} ({volts:g}V) -> NICHICON {cap_res['primary_recommendation']} ({cap_res['recommended_voltage_v']:g}V) ]",
                flashcard_title=f"CAPACITOR TRANSLATION: {code}",
                flashcard_diagram=(
                    f"  SCHEMATIC CODE : {code} ({cap_res.get('original_type', 'Electrolytic')})\n"
                    f"  MODERN SERIES  : Nichicon {', '.join(cap_res['modern_nichicon_series'])}\n"
                    f"  VOLTAGE RULE   : {cap_res['original_voltage_v']:g}V -> {cap_res['recommended_voltage_v']:g}V\n"
                    f"  APPLICATION    : {cap_res['application_rule']}"
                ),
            )

        elif any(k in p_lower for k in ("screw", "bin a", "bin b", "bin c", "tray", "butler")):
            target_bin = "Bin A"
            if "bin b" in p_lower:
                target_bin = "Bin B"
            elif "bin c" in p_lower:
                target_bin = "Bin C"
            delta = -1 if "remove" in p_lower or "take" in p_lower else 4
            tray = "RETRACTED" if "retract" in p_lower else "EXTENDED"
            self.control_vern_hardware(
                hud_mode="MODE_4_SCREW_BUTLER",
                tray_state=tray,
                bin_label=target_bin,
                screw_delta=delta,
                screw_description="Faceplate & Bonnet M4 Machine Screws",
                arm_emote="present_tray",
                unit_id=unit_id,
            )
            tool_results["screw_bins"] = self.db.get_screw_bins(unit_id)

        # 2. Cloud Gemini Call if configured & requested
        model_used = self.select_model(deep_schematic=deep_schematic)
        if prefer_cloud and (self.api_key or self._client is not None):
            try:
                resp = self.client.models.generate_content(
                    model=model_used,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=VERN_SYSTEM_INSTRUCTION,
                        tools=self.get_tools(),
                        temperature=0.3,
                    ),
                )
                spoken = enforce_spoken_brevity(resp.text or "")
                self.hardware_state.last_spoken_reply = spoken
                self._notify_listeners()
                return {
                    "spoken_reply": spoken,
                    "model_used": model_used,
                    "tool_results": tool_results,
                    "hardware_state": self.hardware_state.to_dict(),
                }
            except Exception as exc:
                tool_results["cloud_fallback_reason"] = str(exc)

        # 3. Deterministic Local Spoken Reply Synthesis (2 to 4 concise sentences)
        spoken = self._synthesize_local_spoken_reply(prompt, tool_results)
        self.hardware_state.last_spoken_reply = spoken
        self._notify_listeners()
        return {
            "spoken_reply": spoken,
            "model_used": f"{model_used} (local-bench-sim)",
            "tool_results": tool_results,
            "hardware_state": self.hardware_state.to_dict(),
        }

    def _synthesize_local_spoken_reply(self, prompt: str, tool_results: dict[str, Any]) -> str:
        if "transistor_lookup" in tool_results:
            spec = tool_results["transistor_lookup"]
            if spec["current_deficit_flagged"]:
                return enforce_spoken_brevity(
                    f"Hold your soldering iron, Lead Engineer! My solid-state memory banks show the original 2SC458 handles 100mA, "
                    f"so a 50mA KSC1845 will suffer a current deficit in that driver stage. "
                    f"Install an Onsemi {spec['recommended_replacement']} or Diodes ZTX694B instead, and rotate 180 degrees from the X-172 tombstone B-C-E pinout."
                )
            if spec["gain_warning_flagged"]:
                return enforce_spoken_brevity(
                    f"Careful on that D-rank 2SC458 position! The global bulletin board system notes require h_FE between 400 and 800, "
                    f"so a KSC1815Y is far too low-gain. Use an Onsemi {spec['recommended_replacement']} rotated 180 degrees from the X-172 tombstone silkscreen, "
                    f"and verify 0.65V diode drops before soldering."
                )
            return enforce_spoken_brevity(
                f"Amaze! For a low-current signal stage under 50mA, replace that noisy 2SC458 with an Onsemi KSC1845F from the computerized mail-order catalog. "
                f"Watch the X-172 tombstone trap on my 8.5-inch phosphor HUD: KSC1845F is E-C-B, so rotate it 180 degrees from B-C-E and verify your diode drops first."
            )

        if "dbt_protocol" in tool_results:
            dbt = tool_results["dbt_protocol"]
            if dbt["dbt_status"] == "SHORT CIRCUIT FAULT":
                return enforce_spoken_brevity(
                    "Danger, Lead Engineer—kill the AC switch immediately! A brightly lit Dim Bulb filament indicates a dead short circuit on the primary or B-plus rail. "
                    "I have locked my turret safety beacon to RED; let us isolate the main rectifier and output transistors before applying power again."
                )
            return enforce_spoken_brevity(
                "Good, good, good! A bright flash dimming to a faint glow means the main filter capacitors charged cleanly with zero dead shorts. "
                "I have set the turret beacon to AMBER; grab your probes so we can log each power rail first in VDC and second in VAC for 120 Hz ripple."
            )

        if "capacitor_lookup" in tool_results:
            cap = tool_results["capacitor_lookup"]
            return enforce_spoken_brevity(
                f"Checking my solid-state memory banks for that {cap['schematic_code']} capacitor specification. "
                f"Install a Nichicon {cap['primary_recommendation']} rated at {cap['recommended_voltage_v']:g}V—{cap['application_rule']}"
            )

        if "screw_bins" in tool_results:
            return enforce_spoken_brevity(
                f"Extending the motorized Screw Butler arms across the microscope stage now. "
                f"I have logged those fasteners into my solid-state memory banks so not a single vintage machine screw goes missing."
            )

        return enforce_spoken_brevity(
            "I hear you loud and clear over your FM lapel telemetry pack, Lead Engineer. "
            "My overhead vidicon tube and solid-state memory banks are ready for your next transistor check, Dim Bulb test, or schematic trace."
        )
