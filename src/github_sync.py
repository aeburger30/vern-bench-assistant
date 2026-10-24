"""GitHub Vault & Automated Restoration Dossiers for V.E.R.N. ('the off-site magnetic tape vault')."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from git import Actor, InvalidGitRepositoryError, Repo

from src.config import (
    DOCS_RESTORATIONS_DIR,
    GITHUB_AUTO_PUSH,
    MODEL_QUIRKS_PATH,
    PROJECT_ROOT,
    WORKBENCH_DB_PATH,
)
from src.workbench_db import WorkbenchDB


def _slugify(value: str) -> str:
    """Convert brand/model/serial strings into a clean filename slug."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return re.sub(r"-{2,}", "-", cleaned).strip("-").lower()


def _format_num(val: Any, suffix: str = "") -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.2f}{suffix}"
    return f"{val}{suffix}"


def render_restoration_dossier_markdown(dossier_data: dict[str, Any]) -> str:
    """Render a comprehensive Markdown restoration dossier from WorkbenchDB records."""
    unit = dossier_data["unit"]
    work_logs = dossier_data["work_logs"]
    replacements = dossier_data["component_replacements"]
    telemetry = dossier_data["test_telemetry"]
    screw_bins = dossier_data["screw_bins"]

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# Restoration Dossier: {unit['brand']} {unit['model']} (S/N `{unit['serial_number']}`)",
        "",
        "> **Archived by V.E.R.N. (Model VS-20501)** — *Second Chance Audio Restoration Log*",
        "",
        "## 1. Unit Metadata",
        "| Field | Value |",
        "| :--- | :--- |",
        f"| **Unit ID** | `{unit['unit_id']}` |",
        f"| **Brand** | {unit['brand']} |",
        f"| **Model** | {unit['model']} |",
        f"| **Serial Number** | `{unit['serial_number']}` |",
        f"| **Service Manual Path** | `{unit.get('manual_local_path') or 'Not linked'}` |",
        f"| **Dossier Generated** | {now_str} |",
        "",
        "## 2. Dim Bulb Tester (DBT) & Dual-Pass Power Supply Telemetry",
    ]

    if telemetry:
        lines.extend(
            [
                "| Pass # | DBT Status | B+ Rail (`VDC`) | 120 Hz Ripple (`VAC`) | Idle Bias (`mA`) | Pre-THD (`%`) | Post-THD (`%`) |",
                "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            ]
        )
        for idx, t in enumerate(telemetry, start=1):
            lines.append(
                f"| {idx} | **{t['dbt_status']}** | {_format_num(t['b_plus_vdc'], ' V')} "
                f"| {_format_num(t['ripple_vac_120hz'], ' V')} | {_format_num(t['idle_bias_ma'], ' mA')} "
                f"| {_format_num(t['pre_thd_pct'], '%')} | {_format_num(t['post_thd_pct'], '%')} |"
            )
    else:
        lines.append("*No power supply or DBT telemetry recorded yet.*")

    lines.extend(
        [
            "",
            "## 3. Component Replacements & Pinout Verification Log",
        ]
    )

    if replacements:
        lines.extend(
            [
                "| Designator | Original Part | Measured Fault / Condition | Replacement Installed | Pinout Verified |",
                "| :--- | :--- | :--- | :--- | :---: |",
            ]
        )
        for comp in replacements:
            check = "[x] Verified" if comp["pinout_verified"] else "[ ] Unverified"
            lines.append(
                f"| `{comp['schematic_designator']}` | `{comp['original_part']}` "
                f"| {comp['fault_metric']} | `{comp['replacement_part']}` | {check} |"
            )
    else:
        lines.append("*No component replacements logged yet.*")

    lines.extend(
        [
            "",
            "## 4. Screw Butler Fastener Audit",
            "| Bin | Count | Fastener Location / Description | Tray State | Last Updated |",
            "| :--- | :---: | :--- | :---: | :--- |",
        ]
    )
    for b in screw_bins:
        lines.append(
            f"| **{b['bin_label']}** | `{b['screw_count']}` | {b['description']} "
            f"| `{b['tray_state']}` | {b['updated_ts']} |"
        )

    lines.extend(
        [
            "",
            "## 5. Chronological Bench Notes",
        ]
    )
    if work_logs:
        for log in work_logs:
            attachment_str = (
                f" *(Media: `{log['media_attachment_path']}`)*"
                if log.get("media_attachment_path")
                else ""
            )
            lines.append(
                f"- **`[{log['timestamp']}]` ({log['entry_type']}):** {log['narrative_notes']}{attachment_str}"
            )
    else:
        lines.append("*No bench notes recorded.*")

    lines.append("")
    return "\n".join(lines)


def _get_or_init_repo(repo_root: Path) -> Repo:
    try:
        return Repo(str(repo_root))
    except InvalidGitRepositoryError:
        return Repo.init(str(repo_root))


def publish_restoration_dossier(
    unit_id: int,
    commit_message: str,
    db_path: str | Path | None = None,
    repo_path: str | Path | None = None,
    push: bool | None = None,
) -> dict[str, Any]:
    """Generate Markdown Restoration Dossier for `unit_id`, stage, commit, and optionally push."""
    effective_repo_root = Path(repo_path) if repo_path is not None else PROJECT_ROOT
    effective_db_path = Path(db_path) if db_path is not None else WORKBENCH_DB_PATH
    should_push = GITHUB_AUTO_PUSH if push is None else push

    db = WorkbenchDB(effective_db_path)
    dossier_data = db.get_unit_dossier_data(unit_id)
    unit = dossier_data["unit"]

    slug_filename = (
        f"{_slugify(unit['brand'])}-{_slugify(unit['model'])}-{_slugify(unit['serial_number'])}.md"
    )
    restorations_dir = effective_repo_root / "docs" / "restorations"
    restorations_dir.mkdir(parents=True, exist_ok=True)
    dossier_path = restorations_dir / slug_filename

    markdown_body = render_restoration_dossier_markdown(dossier_data)
    dossier_path.write_text(markdown_body, encoding="utf-8")

    # Ensure knowledge/model_quirks.md exists in repo_root
    quirks_path = effective_repo_root / "knowledge" / "model_quirks.md"
    quirks_path.parent.mkdir(parents=True, exist_ok=True)
    if not quirks_path.exists():
        if MODEL_QUIRKS_PATH.exists():
            quirks_path.write_text(MODEL_QUIRKS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            quirks_path.write_text("# V.E.R.N. Bench Field Notes & Model Quirks\n", encoding="utf-8")

    repo = _get_or_init_repo(effective_repo_root)
    rel_dossier = str(dossier_path.relative_to(effective_repo_root))
    rel_quirks = str(quirks_path.relative_to(effective_repo_root))
    repo.index.add([rel_dossier, rel_quirks])

    author = Actor("V.E.R.N. (VS-20501)", "vern@secondchanceaudio.local")
    commit = repo.index.commit(commit_message, author=author, committer=author)

    pushed = False
    push_error = None
    if should_push and repo.remotes:
        try:
            repo.remotes.origin.push()
            pushed = True
        except Exception as exc:
            push_error = str(exc)

    return {
        "status": "published",
        "unit_id": unit_id,
        "dossier_path": str(dossier_path),
        "relative_dossier_path": rel_dossier,
        "commit_sha": commit.hexsha,
        "commit_message": commit_message,
        "pushed_to_remote": pushed,
        "push_error": push_error,
        "vern_anachronism": "Punched a permanent revision card into the off-site magnetic tape vault.",
    }


def log_bench_quirk(
    model: str,
    quirk_note: str,
    repo_path: str | Path | None = None,
    push: bool | None = None,
) -> dict[str, Any]:
    """Append a circuit quirk or service bulletin note to `knowledge/model_quirks.md` and commit."""
    effective_repo_root = Path(repo_path) if repo_path is not None else PROJECT_ROOT
    should_push = GITHUB_AUTO_PUSH if push is None else push

    quirks_path = effective_repo_root / "knowledge" / "model_quirks.md"
    quirks_path.parent.mkdir(parents=True, exist_ok=True)
    if not quirks_path.exists():
        quirks_path.write_text(
            "# V.E.R.N. Bench Field Notes & Model Quirks (`VS-20501`)\n\n",
            encoding="utf-8",
        )

    existing = quirks_path.read_text(encoding="utf-8")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry_block = f"\n## {model.strip()} ({timestamp})\n- {quirk_note.strip()}\n"
    quirks_path.write_text(existing.rstrip() + "\n" + entry_block, encoding="utf-8")

    repo = _get_or_init_repo(effective_repo_root)
    rel_quirks = str(quirks_path.relative_to(effective_repo_root))
    repo.index.add([rel_quirks])

    author = Actor("V.E.R.N. (VS-20501)", "vern@secondchanceaudio.local")
    commit_msg = f"Field quirk logged for {model.strip()}: {quirk_note.strip()[:50]}"
    commit = repo.index.commit(commit_msg, author=author, committer=author)

    pushed = False
    if should_push and repo.remotes:
        try:
            repo.remotes.origin.push()
            pushed = True
        except Exception:
            pushed = False

    return {
        "status": "logged",
        "model": model.strip(),
        "quirk_note": quirk_note.strip(),
        "quirks_file": str(quirks_path),
        "commit_sha": commit.hexsha,
        "pushed_to_remote": pushed,
    }
