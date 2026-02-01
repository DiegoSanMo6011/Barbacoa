from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime


class OfflineStore:
    def __init__(self, base_dir: str):
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "offline.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS offline_ops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    op TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def enqueue(self, op: str, payload: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO offline_ops (op, payload, created_at) VALUES (?, ?, ?)",
                (op, json.dumps(payload, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()

    def list_ops(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            rows = cur.execute("SELECT id, op, payload, created_at FROM offline_ops ORDER BY id").fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "op": row[1],
                "payload": json.loads(row[2]),
                "created_at": row[3],
            })
        return result

    def delete_op(self, op_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM offline_ops WHERE id = ?", (op_id,))
            conn.commit()

    def daily_backup(self, base_dir: str) -> None:
        backup_dir = os.path.join(base_dir, "data", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(backup_dir, f"offline_{stamp}.json")
        if os.path.exists(path):
            return
        data = {"generated_at": datetime.now().isoformat(timespec="seconds"), "ops": self.list_ops()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
