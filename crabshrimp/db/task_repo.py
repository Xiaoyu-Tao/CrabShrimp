import sqlite3
from datetime import datetime, timezone


class TaskRepository:
    """任务摘要的 SQLite 持久化层，供 Shell-Molting 跨任务查询。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(
        self,
        task_id: str,
        description: str,
        category: str,
        stopped_early: bool,
        steps_count: int,
        trace_path: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO task_records
                (task_id, description, category, stopped_early, steps_count, trace_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                description,
                category,
                1 if stopped_early else 0,
                steps_count,
                trace_path,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM task_records").fetchone()[0]
