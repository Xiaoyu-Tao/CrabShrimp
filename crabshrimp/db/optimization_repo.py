import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Tuple


class OptimizationRepository:
    """Prompt optimizations 的 SQLite 持久化层。"""

    MAX_PER_SLOT = 5  # 每个 (role, task_category) 最多保留 N 条优化建议

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(
        self,
        role: str,
        task_category: str,
        patch: str,
        source_task_id: str,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO prompt_optimizations
                (role, task_category, patch, source_task_id, usage_count, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (role, task_category, patch, source_task_id,
             datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_top(
        self, role: str, task_category: str, limit: int = 1
    ) -> List[Tuple[int, str]]:
        """按 usage_count 降序取前 N 条，返回 [(id, patch), ...]。"""
        rows = self._conn.execute(
            """
            SELECT id, patch FROM prompt_optimizations
            WHERE role = ? AND task_category = ?
            ORDER BY usage_count DESC, created_at DESC
            LIMIT ?
            """,
            (role, task_category, limit),
        ).fetchall()
        return [(row["id"], row["patch"]) for row in rows]

    def increment_usage(self, opt_id: int) -> None:
        self._conn.execute(
            "UPDATE prompt_optimizations SET usage_count = usage_count + 1 WHERE id = ?",
            (opt_id,),
        )
        self._conn.commit()

    def count_by_role_category(self, role: str, task_category: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM prompt_optimizations WHERE role = ? AND task_category = ?",
            (role, task_category),
        ).fetchone()
        return row[0]
