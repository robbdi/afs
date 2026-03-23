from __future__ import annotations

import base64
import sqlite3
from pathlib import Path

from afs.antigravity_status import antigravity_status


def test_antigravity_status_reports_missing_database(tmp_path: Path) -> None:
    status = antigravity_status(db_path=tmp_path / "missing.vscdb")

    assert status["db_exists"] is False
    assert status["payload_count"] == 0
    assert status["error"] == "database not found"


def test_antigravity_status_counts_decodable_payloads(tmp_path: Path) -> None:
    db_path = tmp_path / "state.vscdb"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE ItemTable (key TEXT, value TEXT)")
        connection.execute(
            "INSERT INTO ItemTable(key, value) VALUES (?, ?)",
            (
                "antigravityUnifiedStateSync.trajectorySummaries",
                base64.b64encode(b"{\"ok\":true}").decode("ascii"),
            ),
        )
        connection.commit()

    status = antigravity_status(db_path=db_path)

    assert status["db_exists"] is True
    assert status["payload_count"] == 1
    assert status["last_sync"] is not None
    assert status["error"] is None
