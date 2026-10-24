"""Unit tests for V.E.R.N.'s SQLite telemetry schema and CRUD helpers (src/workbench_db.py)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.workbench_db import WorkbenchDB


def test_schema_initialization_and_screw_bins(tmp_path: Path) -> None:
    db_file = tmp_path / "test_workbench.db"
    db = WorkbenchDB(db_file)

    bins = db.get_screw_bins()
    assert len(bins) == 3
    assert [b["bin_label"] for b in bins] == ["Bin A", "Bin B", "Bin C"]
    assert all(b["screw_count"] == 0 for b in bins)
    assert all(b["tray_state"] == "RETRACTED" for b in bins)


def test_unit_crud_and_48hr_files_api_expiry(tmp_path: Path) -> None:
    db = WorkbenchDB(tmp_path / "test_workbench.db")
    unit_id = db.create_unit(
        brand="Pioneer",
        model="SX-780",
        serial_number="YJ8402911",
        manual_local_path="G:/My Drive/Manuals/Pioneer_SX-780.pdf",
    )
    assert unit_id == 1

    unit = db.get_unit(unit_id)
    assert unit is not None
    assert unit["brand"] == "Pioneer"
    assert unit["model"] == "SX-780"
    assert not db.is_manual_uri_valid(unit_id)

    now = 1_700_000_000.0
    expiry = db.update_unit_manual_uri(
        unit_id,
        gemini_file_uri="https://generativelanguage.googleapis.com/v1beta/files/sx780-pdf",
        expiry_ts=now + (47.5 * 3600.0),
    )
    assert expiry == pytest.approx(now + 171000.0)
    assert db.is_manual_uri_valid(unit_id, now_ts=now + 3600.0)
    assert not db.is_manual_uri_valid(unit_id, now_ts=now + (48.0 * 3600.0))


def test_full_restoration_telemetry_and_screw_butler(tmp_path: Path) -> None:
    db = WorkbenchDB(tmp_path / "test_workbench.db")
    unit_id = db.create_unit("Kenwood", "KA-6000", "610492")

    # 1. Work log
    log_id = db.add_work_log(
        unit_id=unit_id,
        entry_type="INSPECTION",
        narrative_notes="Found original X-172 tombstone 2SC458D transistors on tone board with blackened leads.",
    )
    assert log_id == 1

    # 2. Component replacement & pinout verification
    comp_id = db.log_component_replacement(
        unit_id=unit_id,
        schematic_designator="Q101",
        original_part="2SC458D (X-172)",
        fault_metric="Popcorn crackle, h_FE drifted to 95",
        replacement_part="KSC1845F",
        pinout_verified=False,
    )
    db.verify_component_pinout(comp_id, verified=True)
    replacements = db.get_component_replacements(unit_id)
    assert len(replacements) == 1
    assert replacements[0]["pinout_verified"] is True

    # 3. Test telemetry (DBT & Dual-Pass Rail Logging)
    test_id = db.log_test_telemetry(
        unit_id=unit_id,
        dbt_status="PASS",
        b_plus_vdc=56.4,
        ripple_vac_120hz=0.015,
        idle_bias_ma=24.5,
        pre_thd_pct=0.42,
        post_thd_pct=0.04,
    )
    assert test_id == 1

    # 4. Screw Butler updates
    updated_bin = db.update_screw_bin(
        bin_label="Bin A",
        unit_id=unit_id,
        screw_delta=6,
        description="Top walnut cabinet M4 black oxide screws",
        tray_state="EXTENDED",
    )
    assert updated_bin["screw_count"] == 6
    assert updated_bin["tray_state"] == "EXTENDED"

    # Full dossier aggregation
    dossier = db.get_unit_dossier_data(unit_id)
    assert dossier["unit"]["model"] == "KA-6000"
    assert len(dossier["work_logs"]) == 1
    assert len(dossier["component_replacements"]) == 1
    assert len(dossier["test_telemetry"]) == 1
    assert dossier["screw_bins"][0]["screw_count"] == 6
