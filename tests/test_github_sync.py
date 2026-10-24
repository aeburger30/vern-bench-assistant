"""Unit tests for V.E.R.N.'s GitHub Vault & Automated Restoration Dossiers (src/github_sync.py)."""

from __future__ import annotations

from pathlib import Path

from git import Repo

from src.github_sync import log_bench_quirk, publish_restoration_dossier
from src.workbench_db import WorkbenchDB


def test_publish_restoration_dossier_and_git_commit(tmp_path: Path) -> None:
    repo_root = tmp_path / "mock_repo"
    repo_root.mkdir(parents=True)
    Repo.init(str(repo_root))

    db_file = tmp_path / "workbench.db"
    db = WorkbenchDB(db_file)
    unit_id = db.create_unit(
        brand="Sansui",
        model="AU-717",
        serial_number="228041099",
        manual_local_path="G:/My Drive/Manuals/Sansui_AU-717.pdf",
    )
    db.add_work_log(
        unit_id=unit_id,
        entry_type="RESTORATION",
        narrative_notes="Removed corrosive assembly glue from F-2663 power supply board.",
    )
    db.log_component_replacement(
        unit_id=unit_id,
        schematic_designator="TR01",
        original_part="2SC458 (X-172)",
        fault_metric="Noisy phono eq stage",
        replacement_part="KSC1845F",
        pinout_verified=True,
    )
    db.log_test_telemetry(
        unit_id=unit_id,
        dbt_status="PASS",
        b_plus_vdc=63.2,
        ripple_vac_120hz=0.008,
        idle_bias_ma=20.0,
        pre_thd_pct=0.25,
        post_thd_pct=0.015,
    )
    db.update_screw_bin(
        bin_label="Bin B",
        unit_id=unit_id,
        screw_count=8,
        description="Bottom chassis plate M3 screws",
        tray_state="EXTENDED",
    )

    res = publish_restoration_dossier(
        unit_id=unit_id,
        commit_message="Publish Sansui AU-717 restoration dossier",
        db_path=db_file,
        repo_path=repo_root,
        push=False,
    )
    assert res["status"] == "published"
    assert len(res["commit_sha"]) == 40

    dossier_path = Path(res["dossier_path"])
    assert dossier_path.exists()
    assert dossier_path.name == "sansui-au-717-228041099.md"

    content = dossier_path.read_text(encoding="utf-8")
    assert "Sansui AU-717" in content
    assert "PASS" in content
    assert "63.20 V" in content
    assert "KSC1845F" in content
    assert "[x] Verified" in content
    assert "Bottom chassis plate M3 screws" in content


def test_log_bench_quirk_commits_to_model_quirks_md(tmp_path: Path) -> None:
    repo_root = tmp_path / "quirk_repo"
    repo_root.mkdir(parents=True)
    Repo.init(str(repo_root))

    res = log_bench_quirk(
        model="Marantz 2270",
        quirk_note="Early serials (<3900) require updated bias diode thermally mounted to main heatsink.",
        repo_path=repo_root,
        push=False,
    )
    assert res["status"] == "logged"
    quirks_path = Path(res["quirks_file"])
    assert quirks_path.exists()
    text = quirks_path.read_text(encoding="utf-8")
    assert "Marantz 2270" in text
    assert "Early serials (<3900)" in text
