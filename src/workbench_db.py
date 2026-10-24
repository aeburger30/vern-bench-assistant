"""SQLite telemetry schema and CRUD operations for V.E.R.N. ('solid-state memory banks')."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.config import (
    FILES_API_TTL_SECONDS,
    SCREW_BIN_LABELS,
    VALID_TRAY_STATES,
    WORKBENCH_DB_PATH,
)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS units (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    serial_number TEXT NOT NULL,
    manual_local_path TEXT DEFAULT '',
    gemini_file_uri TEXT DEFAULT '',
    uri_expiry_ts REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS work_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    narrative_notes TEXT NOT NULL,
    media_attachment_path TEXT DEFAULT '',
    FOREIGN KEY (unit_id) REFERENCES units(unit_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS component_replacements (
    comp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    schematic_designator TEXT NOT NULL,
    original_part TEXT NOT NULL,
    fault_metric TEXT NOT NULL,
    replacement_part TEXT NOT NULL,
    pinout_verified BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (unit_id) REFERENCES units(unit_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS test_telemetry (
    test_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    dbt_status TEXT NOT NULL,
    b_plus_vdc REAL,
    ripple_vac_120hz REAL,
    idle_bias_ma REAL,
    pre_thd_pct REAL,
    post_thd_pct REAL,
    FOREIGN KEY (unit_id) REFERENCES units(unit_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS screw_bins (
    bin_label TEXT PRIMARY KEY CHECK (bin_label IN ('Bin A', 'Bin B', 'Bin C')),
    unit_id INTEGER,
    screw_count INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT 'Empty',
    tray_state TEXT NOT NULL DEFAULT 'RETRACTED' CHECK (tray_state IN ('EXTENDED', 'RETRACTED')),
    updated_ts TEXT NOT NULL,
    FOREIGN KEY (unit_id) REFERENCES units(unit_id) ON DELETE SET NULL
);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorkbenchDB:
    """Relational SQLite interface for V.E.R.N.'s solid-state memory banks."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else WORKBENCH_DB_PATH
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Create all 5 relational tables and seed Bin A, Bin B, Bin C if missing."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        now_iso = _utc_now_iso()
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            for label in SCREW_BIN_LABELS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO screw_bins
                        (bin_label, unit_id, screw_count, description, tray_state, updated_ts)
                    VALUES (?, NULL, 0, 'Empty', 'RETRACTED', ?)
                    """,
                    (label, now_iso),
                )

    # ------------------------------------------------------------------
    # 1. Units Table CRUD & 48-Hour Files API URI Tracking
    # ------------------------------------------------------------------
    def create_unit(
        self,
        brand: str,
        model: str,
        serial_number: str,
        manual_local_path: str = "",
        gemini_file_uri: str = "",
        uri_expiry_ts: float = 0.0,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO units
                    (brand, model, serial_number, manual_local_path, gemini_file_uri, uri_expiry_ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    brand.strip(),
                    model.strip(),
                    serial_number.strip(),
                    manual_local_path,
                    gemini_file_uri,
                    float(uri_expiry_ts),
                ),
            )
            return int(cur.lastrowid)

    def get_unit(self, unit_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM units WHERE unit_id = ?", (unit_id,)).fetchone()
            return dict(row) if row else None

    def list_units(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM units ORDER BY unit_id ASC").fetchall()
            return [dict(r) for r in rows]

    def update_unit_manual_uri(
        self,
        unit_id: int,
        gemini_file_uri: str,
        expiry_ts: float | None = None,
    ) -> float:
        """Store uploaded Gemini Files API URI and expiry timestamp (default now + 47.5h)."""
        effective_expiry = (
            float(expiry_ts)
            if expiry_ts is not None
            else (time.time() + FILES_API_TTL_SECONDS)
        )
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE units
                SET gemini_file_uri = ?, uri_expiry_ts = ?
                WHERE unit_id = ?
                """,
                (gemini_file_uri, effective_expiry, unit_id),
            )
        return effective_expiry

    def is_manual_uri_valid(self, unit_id: int, now_ts: float | None = None) -> bool:
        """Check whether the unit has a non-empty Gemini Files API URI that has not expired."""
        unit = self.get_unit(unit_id)
        if not unit or not unit.get("gemini_file_uri"):
            return False
        current_time = now_ts if now_ts is not None else time.time()
        return float(unit.get("uri_expiry_ts") or 0.0) > current_time

    # ------------------------------------------------------------------
    # 2. Work Logs Table CRUD
    # ------------------------------------------------------------------
    def add_work_log(
        self,
        unit_id: int,
        entry_type: str,
        narrative_notes: str,
        media_attachment_path: str = "",
        timestamp: str | None = None,
    ) -> int:
        ts = timestamp or _utc_now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO work_logs
                    (unit_id, timestamp, entry_type, narrative_notes, media_attachment_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (unit_id, ts, entry_type.strip(), narrative_notes.strip(), media_attachment_path),
            )
            return int(cur.lastrowid)

    def get_work_logs(self, unit_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM work_logs WHERE unit_id = ? ORDER BY log_id ASC",
                (unit_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # 3. Component Replacements Table CRUD
    # ------------------------------------------------------------------
    def log_component_replacement(
        self,
        unit_id: int,
        schematic_designator: str,
        original_part: str,
        fault_metric: str,
        replacement_part: str,
        pinout_verified: bool = False,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO component_replacements
                    (unit_id, schematic_designator, original_part, fault_metric, replacement_part, pinout_verified)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    schematic_designator.strip(),
                    original_part.strip(),
                    fault_metric.strip(),
                    replacement_part.strip(),
                    1 if pinout_verified else 0,
                ),
            )
            return int(cur.lastrowid)

    def verify_component_pinout(self, comp_id: int, verified: bool = True) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE component_replacements SET pinout_verified = ? WHERE comp_id = ?",
                (1 if verified else 0, comp_id),
            )

    def get_component_replacements(self, unit_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM component_replacements WHERE unit_id = ? ORDER BY comp_id ASC",
                (unit_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["pinout_verified"] = bool(d["pinout_verified"])
                result.append(d)
            return result

    # ------------------------------------------------------------------
    # 4. Test Telemetry Table CRUD (DBT & Dual-Pass Rail Logging)
    # ------------------------------------------------------------------
    def log_test_telemetry(
        self,
        unit_id: int,
        dbt_status: str,
        b_plus_vdc: float | None = None,
        ripple_vac_120hz: float | None = None,
        idle_bias_ma: float | None = None,
        pre_thd_pct: float | None = None,
        post_thd_pct: float | None = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO test_telemetry
                    (unit_id, dbt_status, b_plus_vdc, ripple_vac_120hz, idle_bias_ma, pre_thd_pct, post_thd_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    dbt_status.strip().upper(),
                    b_plus_vdc,
                    ripple_vac_120hz,
                    idle_bias_ma,
                    pre_thd_pct,
                    post_thd_pct,
                ),
            )
            return int(cur.lastrowid)

    def get_test_telemetry(self, unit_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM test_telemetry WHERE unit_id = ? ORDER BY test_id ASC",
                (unit_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # 5. Screw Bins ("Screw Butler") CRUD
    # ------------------------------------------------------------------
    def update_screw_bin(
        self,
        bin_label: str,
        unit_id: int | None = None,
        screw_count: int | None = None,
        screw_delta: int = 0,
        description: str | None = None,
        tray_state: str | None = None,
    ) -> dict[str, Any]:
        if bin_label not in SCREW_BIN_LABELS:
            raise ValueError(f"Invalid bin_label '{bin_label}'. Must be one of {SCREW_BIN_LABELS}.")
        if tray_state is not None and tray_state not in VALID_TRAY_STATES:
            raise ValueError(f"Invalid tray_state '{tray_state}'. Must be one of {VALID_TRAY_STATES}.")

        now_iso = _utc_now_iso()
        with self.connect() as conn:
            current = dict(
                conn.execute(
                    "SELECT * FROM screw_bins WHERE bin_label = ?", (bin_label,)
                ).fetchone()
            )
            new_unit_id = unit_id if unit_id is not None else current["unit_id"]
            if screw_count is not None:
                new_count = max(0, int(screw_count))
            else:
                new_count = max(0, int(current["screw_count"]) + int(screw_delta))
            new_desc = description if description is not None else current["description"]
            new_tray = tray_state if tray_state is not None else current["tray_state"]

            conn.execute(
                """
                UPDATE screw_bins
                SET unit_id = ?, screw_count = ?, description = ?, tray_state = ?, updated_ts = ?
                WHERE bin_label = ?
                """,
                (new_unit_id, new_count, new_desc, new_tray, now_iso, bin_label),
            )
            if tray_state is not None:
                # Physical tray moves all 3 bins together on the microscope stage
                conn.execute(
                    "UPDATE screw_bins SET tray_state = ?, updated_ts = ?",
                    (tray_state, now_iso),
                )
            updated = conn.execute(
                "SELECT * FROM screw_bins WHERE bin_label = ?", (bin_label,)
            ).fetchone()
            return dict(updated)

    def set_screw_tray_state(self, tray_state: str) -> list[dict[str, Any]]:
        if tray_state not in VALID_TRAY_STATES:
            raise ValueError(f"Invalid tray_state '{tray_state}'. Must be one of {VALID_TRAY_STATES}.")
        now_iso = _utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                "UPDATE screw_bins SET tray_state = ?, updated_ts = ?",
                (tray_state, now_iso),
            )
        return self.get_screw_bins()

    def get_screw_bins(self, unit_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if unit_id is not None:
                rows = conn.execute(
                    "SELECT * FROM screw_bins WHERE unit_id = ? OR unit_id IS NULL ORDER BY bin_label ASC",
                    (unit_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM screw_bins ORDER BY bin_label ASC"
                ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Full Dossier Query Aggregation
    # ------------------------------------------------------------------
    def get_unit_dossier_data(self, unit_id: int) -> dict[str, Any]:
        unit = self.get_unit(unit_id)
        if not unit:
            raise ValueError(f"Unit ID {unit_id} not found in workbench.db.")
        return {
            "unit": unit,
            "work_logs": self.get_work_logs(unit_id),
            "component_replacements": self.get_component_replacements(unit_id),
            "test_telemetry": self.get_test_telemetry(unit_id),
            "screw_bins": self.get_screw_bins(unit_id),
        }
