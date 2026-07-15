"""Characterization tests for the SQLite paths of core.db.

Google Sheets and the process-level st.cache_resource paths are out of scope
here (they need network / a Streamlit runtime); the local SQLite backend is the
deterministic fallback and is what these tests lock.
"""
from __future__ import annotations

from datetime import date

import pytest

from core import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point the module-level DB_PATH at an isolated temp file per test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "history.db")
    yield


# ── _filter_excluded ──────────────────────────────────────────────────────────
class TestFilterExcluded:
    def test_removes_excluded_farmers(self):
        state = {
            "farmers_data": {
                "fanny.landazabal@rappi.com": {"x": 1},
                "luis.ibarra@rappi.com": {"x": 2},  # in EXCLUDED_EMAILS
            }
        }
        out = db._filter_excluded(state)
        assert "luis.ibarra@rappi.com" not in out["farmers_data"]
        assert "fanny.landazabal@rappi.com" in out["farmers_data"]

    def test_does_not_mutate_input(self):
        state = {"farmers_data": {"luis.ibarra@rappi.com": {"x": 2}}}
        db._filter_excluded(state)
        # original dict is untouched
        assert "luis.ibarra@rappi.com" in state["farmers_data"]

    def test_missing_farmers_data_key_is_safe(self):
        assert db._filter_excluded({}) == {}


# ── SQLite snapshot round-trip ────────────────────────────────────────────────
class TestSnapshotRoundTrip:
    def test_save_then_get(self):
        fd = {
            "fanny.landazabal@rappi.com": {"ATT_MD_Total": 0.73, "name": "Fanny"},
            "alejandro.salamanca@rappi.com": {"ATT_MD_Total": 0.68, "name": "Alex"},
        }
        db._save_sqlite(date(2026, 7, 14), dia_corte=13, farmers_data=fd)
        rows = db._get_sqlite()
        assert len(rows) == 2
        emails = {r["ATT_MD_Total"] for r in rows}
        assert 0.73 in emails and 0.68 in emails
        assert all(r["snap_date"] == "2026-07-14" for r in rows)
        assert all(r["dia_corte"] == 13 for r in rows)

    def test_save_is_idempotent_per_date_and_farmer(self):
        fd1 = {"fanny.landazabal@rappi.com": {"v": 1}}
        fd2 = {"fanny.landazabal@rappi.com": {"v": 2}}
        db._save_sqlite(date(2026, 7, 14), 13, fd1)
        db._save_sqlite(date(2026, 7, 14), 13, fd2)  # same date+farmer overwrites
        rows = db._get_sqlite(farmer="fanny.landazabal@rappi.com")
        assert len(rows) == 1
        assert rows[0]["v"] == 2

    def test_get_dates(self):
        db._save_sqlite(date(2026, 7, 7), 6, {"f@rappi.com": {}})
        db._save_sqlite(date(2026, 7, 14), 13, {"f@rappi.com": {}})
        dates = db._get_dates_sqlite()
        assert dates == ["2026-07-14", "2026-07-07"]  # DESC order


# ── WBR checklist upsert ──────────────────────────────────────────────────────
class TestChecklist:
    def test_upsert_and_read(self):
        db.save_checklist_task("2026-W29", "task_a", True)
        db.save_checklist_task("2026-W29", "task_b", False)
        state = db.get_checklist_state("2026-W29")
        assert state == {"task_a": True, "task_b": False}

    def test_upsert_overwrites(self):
        db.save_checklist_task("2026-W29", "task_a", True)
        db.save_checklist_task("2026-W29", "task_a", False)
        assert db.get_checklist_state("2026-W29") == {"task_a": False}


# ── WBR llamados de atención ───────────────────────────────────────────────────
class TestLlamados:
    def test_save_and_delete(self):
        db.save_llamado("fanny.landazabal@rappi.com", 1, "2026-07-14",
                        "motivo x", "Manpower")
        rows = db.get_all_llamados()
        assert len(rows) == 1
        assert rows[0]["numero"] == 1
        assert rows[0]["tipo_contrato"] == "Manpower"

        db.delete_llamado(rows[0]["id"])
        assert db.get_all_llamados() == []
