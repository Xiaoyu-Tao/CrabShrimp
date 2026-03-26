import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional


class SkillRepository:
    """Skill 知识库的 SQLite 持久化层。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(
        self,
        role: str,
        task_category: str,
        content: str,
        source_task_id: str,
    ) -> str:
        skill_id = str(uuid.uuid4())[:8]
        self._conn.execute(
            """
            INSERT INTO skills (skill_id, role, task_category, content, source_task_id, usage_count, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (
                skill_id,
                role,
                task_category,
                content,
                source_task_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()
        return skill_id

    def get_top_skills(
        self, role: str, task_category: str, limit: int = 3
    ) -> List[tuple]:
        """
        按 usage_count 降序取前 N 条，返回 [(skill_id, content), ...] 列表。
        调用方在注入后应调用 increment_usage() 反馈使用次数。
        """
        rows = self._conn.execute(
            """
            SELECT skill_id, content FROM skills
            WHERE role = ? AND task_category = ?
            ORDER BY usage_count DESC, created_at DESC
            LIMIT ?
            """,
            (role, task_category, limit),
        ).fetchall()
        return [(row["skill_id"], row["content"]) for row in rows]

    def increment_usage(self, skill_id: str) -> None:
        self._conn.execute(
            "UPDATE skills SET usage_count = usage_count + 1 WHERE skill_id = ?",
            (skill_id,),
        )
        self._conn.commit()

    def count_by_role_category(self, role: str, task_category: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM skills WHERE role = ? AND task_category = ?",
            (role, task_category),
        ).fetchone()
        return row[0]
