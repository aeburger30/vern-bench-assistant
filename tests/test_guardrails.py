"""Unit tests for V.E.R.N.'s vintage audio engineering guardrails, Cloud routing, and Context Caching."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.config import DEEP_SCHEMATIC_MODEL, ROUTINE_MODEL
from src.vern_agent import (
    VernAgent,
    check_distributor_stock,
    enforce_spoken_brevity,
    evaluate_dbt_protocol,
    lookup_capacitor_mapping,
    lookup_transistor_specs,
    normalize_distributor_part_number,
)


def test_2sc458_low_current_signal_stage_and_tombstone_pinout_trap() -> None:
    res = lookup_transistor_specs(
        part_number="2SC458LG",
        circuit_stage="phono_preamp",
        stage_current_ma=2.5,
    )
    assert res["found"] is True
    assert res["canonical_part"] == "2SC458"
    assert res["current_deficit_flagged"] is False
    assert res["recommended_replacement"] == "KSC1845F"
    assert res["pinout_trap_active"] is True
    assert res["hud_flashcard_banner"] == "[ KSC1845: E-C-B | ROTATE 180° FROM TOMBSTONE ]"


def test_2sc458_high_current_driver_stage_flags_deficit() -> None:
    res = lookup_transistor_specs(
        part_number="2SC458",
        circuit_stage="driver",
        stage_current_ma=75.0,
    )
    assert res["current_deficit_flagged"] is True
    assert res["recommended_replacement"] == "KSC1815"
    assert res["alternate_replacement"] == "ZTX694B"
    assert any("CURRENT DEFICIT" in w for w in res["warnings"])


def test_2sc458d_high_gain_rank_warns_against_ksc1815y() -> None:
    res = lookup_transistor_specs(
        part_number="2SC458D",
        circuit_stage="phono_preamp",
        stage_current_ma=3.0,
        gain_rank="D",
        proposed_replacement="KSC1815Y",
    )
    assert res["gain_warning_flagged"] is True
    assert res["recommended_replacement"] == "KSC1845F"
    assert any("GAIN RANK WARNING" in w for w in res["warnings"])


def test_distributor_packaging_suffix_stripping() -> None:
    assert normalize_distributor_part_number("KSC1845FTA") == "KSC1845F"
    assert normalize_distributor_part_number("KSC1845FBU") == "KSC1845F"
    assert normalize_distributor_part_number("KSC1815YTA") == "KSC1815Y"
    assert normalize_distributor_part_number("KSA992FTA") == "KSA992F"

    stock = check_distributor_stock("KSC1845FTA")
    assert stock["normalized_base_part"] == "KSC1845F"
    assert stock["status"] == "IN_STOCK"
    assert stock["mouser_stock"] > 0


def test_pioneer_sansui_capacitor_mappings_and_80v_bump() -> None:
    cea = lookup_capacitor_mapping("CEA", voltage_v=35.0, capacitance_uf=47.0)
    assert cea["primary_recommendation"] == "UPW"
    assert "UPM" in cea["modern_nichicon_series"]
    assert cea["voltage_bumped"] is False

    ceanl = lookup_capacitor_mapping("CEANL", voltage_v=50.0, capacitance_uf=2.2)
    assert ceanl["primary_recommendation"] == "UKL"
    assert "UKL" in ceanl["modern_nichicon_series"]
    assert ceanl["film_upgrade_suggestion"] is not None

    cssa = lookup_capacitor_mapping("CSSA", voltage_v=25.0, capacitance_uf=10.0)
    assert cssa["primary_recommendation"] == "UKL"

    rail_80v = lookup_capacitor_mapping("CEA", voltage_v=80.0, capacitance_uf=6800.0)
    assert rail_80v["voltage_bumped"] is True
    assert rail_80v["recommended_voltage_v"] == 100.0


def test_guided_dbt_protocol_pass_and_short_circuit(tmp_path: Path) -> None:
    db_file = tmp_path / "dbt_test.db"
    pass_res = evaluate_dbt_protocol(
        filament_signature="Bright flash then dims to faint glow",
        unit_category="stereo receiver",
        db_path=db_file,
    )
    assert pass_res["dbt_status"] == "PASS"
    assert pass_res["beacon_color"] == "AMBER"
    assert pass_res["recommended_bulb_wattage"] == "60W-100W"

    short_res = evaluate_dbt_protocol(
        filament_signature="Bulb remains brightly lit at full power",
        unit_category="preamp",
        db_path=db_file,
    )
    assert short_res["dbt_status"] == "SHORT CIRCUIT FAULT"
    assert short_res["beacon_color"] == "RED"
    assert short_res["arm_emote"] == "warning_stop"
    assert short_res["recommended_bulb_wattage"] == "25W-40W"


def test_vern_agent_context_caching_and_files_api(tmp_path: Path) -> None:
    mock_client = MagicMock()
    mock_client.files.upload.return_value = SimpleNamespace(
        uri="https://generativelanguage.googleapis.com/v1beta/files/ka6000-manual"
    )
    mock_client.caches.create.return_value = SimpleNamespace(name="cachedContents/vern-cache-001")
    mock_client.caches.update.return_value = SimpleNamespace(name="cachedContents/vern-cache-001")

    agent = VernAgent(db_path=tmp_path / "agent.db", client=mock_client)
    assert agent.select_model(deep_schematic=False) == ROUTINE_MODEL
    assert agent.select_model(deep_schematic=True) == DEEP_SCHEMATIC_MODEL

    # Create a dummy PDF service manual to test 48h Files API Manager
    manual_pdf = tmp_path / "Kenwood_KA-6000.pdf"
    manual_pdf.write_bytes(b"%PDF-1.4 dummy schematic content")
    unit_id = agent.db.create_unit("Kenwood", "KA-6000", "610492", str(manual_pdf))

    uri1 = agent.ensure_manual_uploaded(unit_id, now_ts=1_000_000.0)
    assert uri1 == "https://generativelanguage.googleapis.com/v1beta/files/ka6000-manual"
    assert mock_client.files.upload.call_count == 1

    # Second call within 47.5h window should reuse cached URI without re-uploading
    uri2 = agent.ensure_manual_uploaded(unit_id, now_ts=1_000_000.0 + 3600.0)
    assert uri2 == uri1
    assert mock_client.files.upload.call_count == 1

    # Call after 48h expiry should trigger automatic re-upload
    agent.ensure_manual_uploaded(unit_id, now_ts=1_000_000.0 + (48.0 * 3600.0))
    assert mock_client.files.upload.call_count == 2

    # Explicit Context Caching: skip <= 2048 tokens, create > 2048 tokens
    assert agent.create_schematic_cache(["small snippet"], estimated_tokens=1200) is None
    cache_name = agent.create_schematic_cache(["large multi-page schematic"], estimated_tokens=8500)
    assert cache_name == "cachedContents/vern-cache-001"
    agent.extend_schematic_cache()
    mock_client.caches.update.assert_called_once()
    agent.delete_schematic_cache()
    mock_client.caches.delete.assert_called_once_with(name="cachedContents/vern-cache-001")


def test_spoken_brevity_guardrail() -> None:
    long_text = (
        "Sentence one is here. Sentence two is here. Sentence three is here. "
        "Sentence four is here. Sentence five should be trimmed away. Sentence six too."
    )
    trimmed = enforce_spoken_brevity(long_text)
    sentences = [s for s in trimmed.split(". ") if s]
    assert 2 <= len(sentences) <= 4


def test_retro_hud_four_modes_and_hardware_simulator(tmp_path: Path) -> None:
    from src.audio_router import DualMicRouter
    from src.retro_hud import (
        VernRetroHudApp,
        format_hardware_status_bar,
        render_mode_1_oscilloscope,
        render_mode_2_pinout_flashcard,
        render_mode_3_vision_reticle,
        render_mode_4_screw_butler_toast,
    )
    from src.vision_hub import VisionHub

    agent = VernAgent(db_path=tmp_path / "hud.db")
    mic = DualMicRouter()
    vision = VisionHub()
    uid = agent.db.create_unit("Pioneer", "SX-1050", "WE10293")

    m1 = render_mode_1_oscilloscope(agent, mic)
    assert "1024x768 (4:3)" in m1

    agent.process_bench_command("Check 2SC458 pinout", unit_id=uid, prefer_cloud=False)
    m2 = render_mode_2_pinout_flashcard(agent)
    assert "[ KSC1845: E-C-B | ROTATE 180° FROM TOMBSTONE ]" in m2

    # Test 1.5s Dwell-to-Inspect Watchdog & Dual-Cam Reticle
    assert vision.step_dwell_watchdog(pixel_delta=20.0, dt_seconds=0.1) is None
    assert vision.step_dwell_watchdog(pixel_delta=0.5, dt_seconds=0.8) is None
    snap = vision.step_dwell_watchdog(pixel_delta=0.5, dt_seconds=0.8)
    assert snap is not None
    assert snap.dwell_locked is True

    m3 = render_mode_3_vision_reticle(agent, vision)
    assert "CAM 0: OVERHEAD WIDE VIDICON TUBE" in m3
    assert "CAM 1: MACRO SCANNER" in m3

    agent.control_vern_hardware(
        hud_mode="MODE_4_SCREW_BUTLER",
        tray_state="EXTENDED",
        bin_label="Bin C",
        screw_count=4,
        screw_description="Heat sink M3 machine screws",
        unit_id=uid,
    )
    m4 = render_mode_4_screw_butler_toast(agent, uid)
    assert "Bin C" in m4
    assert "EXTENDED" in m4

    bar = format_hardware_status_bar(agent, vision)
    assert "[SCREW TRAY: EXTENDED]" in bar
    assert "[TURRET BEACON: GREEN]" in bar

    # Verify Textual HUD app instantiation & dial actions
    app = VernRetroHudApp(db_path=tmp_path / "textual_hud.db")
    assert app.agent.hardware_state.hud_mode == "MODE_1_OSCILLOSCOPE"

