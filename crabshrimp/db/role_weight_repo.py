import sqlite3
from typing import List, Tuple


class RoleWeightRepository:
    """
    记录每个 Agent 在各 (task_category, role) 组合下的表现权重。
    wins  = Coral-Meeting 中立场被采纳的次数
    total = 参与 Coral-Meeting 的总次数
    win_rate = wins / total（用于拓扑筛选）
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    @staticmethod
    def _normalize_role(role: str) -> str:
        return role.strip().lower()

    def record_participation(
        self, task_category: str, role: str, agent_id: str
    ) -> None:
        """记录一次会议参与（total + 1）。"""
        role = self._normalize_role(role)
        self._conn.execute(
            """
            INSERT INTO role_weights (task_category, role, agent_id, wins, total)
            VALUES (?, ?, ?, 0, 1)
            ON CONFLICT (task_category, role, agent_id)
            DO UPDATE SET total = total + 1
            """,
            (task_category, role, agent_id),
        )
        self._conn.commit()

    def record_win(
        self, task_category: str, role: str, agent_id: str
    ) -> None:
        """记录一次会议胜出（wins + 1）。"""
        role = self._normalize_role(role)
        self._conn.execute(
            """
            INSERT INTO role_weights (task_category, role, agent_id, wins, total)
            VALUES (?, ?, ?, 1, 1)
            ON CONFLICT (task_category, role, agent_id)
            DO UPDATE SET wins = wins + 1, total = total + 1
            """,
            (task_category, role, agent_id),
        )
        self._conn.commit()

    def win_rate(self, task_category: str, role: str, agent_id: str) -> float:
        """
        返回 agent 在该 (task_category, role) 的历史胜率。
        无记录时返回 1.0（新 Agent 默认满权参与）。
        """
        role = self._normalize_role(role)
        row = self._conn.execute(
            """
            SELECT wins, total FROM role_weights
            WHERE task_category = ? AND role = ? AND agent_id = ?
            """,
            (task_category, role, agent_id),
        ).fetchone()
        if row is None or row["total"] == 0:
            return 1.0
        return row["wins"] / row["total"]

    def get_all_for_category(
        self, task_category: str
    ) -> List[Tuple[str, str, float]]:
        """返回某类别下所有 (role, agent_id, win_rate) 三元组。"""
        rows = self._conn.execute(
            """
            SELECT role, agent_id, wins, total FROM role_weights
            WHERE task_category = ?
            """,
            (task_category,),
        ).fetchall()
        result = []
        for row in rows:
            rate = row["wins"] / row["total"] if row["total"] > 0 else 1.0
            result.append((row["role"], row["agent_id"], rate))
        return result
