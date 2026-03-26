import sqlite3
from datetime import datetime, timezone
from typing import Optional


class MeetingRepository:
    """Coral-Meeting 胜负结果的 SQLite 持久化层，v0.2b 奖惩机制的数据来源。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save_outcome(
        self,
        task_id: str,
        step_id: str,
        winner_agent_id: Optional[str],
        topic: str,
    ) -> None:
        """
        保存一次 Coral-Meeting 的裁决结果。
        winner_agent_id 为 None 表示本次由 LLM 仲裁，无明确胜者。
        """
        self._conn.execute(
            """
            INSERT INTO meeting_outcomes (task_id, step_id, winner_agent_id, topic, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_id,
                step_id,
                winner_agent_id,
                topic,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def wins_by_agent(self, agent_id: str) -> int:
        """查询某 Agent 累计赢得 Coral-Meeting 的次数。"""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM meeting_outcomes WHERE winner_agent_id = ?",
            (agent_id,),
        ).fetchone()
        return row[0]

    def get_winners_for_task(self, task_id: str) -> list[Optional[str]]:
        """返回某任务所有 Coral-Meeting 的 winner_agent_id 列表（None = 仲裁）。"""
        rows = self._conn.execute(
            "SELECT winner_agent_id FROM meeting_outcomes WHERE task_id = ?",
            (task_id,),
        ).fetchall()
        return [row["winner_agent_id"] for row in rows]

    def get_outcomes_for_task(self, task_id: str) -> list[tuple[str, Optional[str]]]:
        """返回某任务所有会议结果的 (step_id, winner_agent_id) 列表。"""
        rows = self._conn.execute(
            """
            SELECT step_id, winner_agent_id
            FROM meeting_outcomes
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()
        return [(row["step_id"], row["winner_agent_id"]) for row in rows]
