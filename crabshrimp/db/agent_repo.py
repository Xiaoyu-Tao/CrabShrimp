import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from crabshrimp.models.agent_profile import (
    AgentProfile, ContextMode, ExecMode, RoleType, WorkspaceMode,
)


class AgentRepository:
    """AgentProfile 的 SQLite 持久化层。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(self, profile: AgentProfile) -> None:
        """插入或更新一条 Agent 档案（upsert）。"""
        self._conn.execute(
            """
            INSERT INTO agent_profiles
                (agent_id, role, system_prompt, contribution_score,
                 context_mode, workspace_mode, exec_mode, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                system_prompt      = excluded.system_prompt,
                contribution_score = excluded.contribution_score,
                context_mode       = excluded.context_mode,
                workspace_mode     = excluded.workspace_mode,
                exec_mode          = excluded.exec_mode,
                updated_at         = excluded.updated_at
            """,
            (
                profile.agent_id,
                profile.role.value,
                profile.system_prompt,
                profile.contribution_score,
                profile.context_mode.value,
                profile.workspace_mode.value,
                profile.exec_mode.value,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def load(self, agent_id: str) -> Optional[AgentProfile]:
        row = self._conn.execute(
            "SELECT * FROM agent_profiles WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        return self._to_profile(row) if row else None

    def load_all(self) -> List[AgentProfile]:
        rows = self._conn.execute("SELECT * FROM agent_profiles").fetchall()
        return [self._to_profile(r) for r in rows]

    def update_contribution(self, agent_id: str, score: float) -> None:
        self._conn.execute(
            "UPDATE agent_profiles SET contribution_score = ?, updated_at = ? WHERE agent_id = ?",
            (score, datetime.now(timezone.utc).isoformat(), agent_id),
        )
        self._conn.commit()

    def _to_profile(self, row: sqlite3.Row) -> AgentProfile:
        return AgentProfile(
            agent_id=row["agent_id"],
            role=RoleType(row["role"]),
            system_prompt=row["system_prompt"],
            contribution_score=row["contribution_score"],
            context_mode=ContextMode(row["context_mode"]),
            workspace_mode=WorkspaceMode(row["workspace_mode"]),
            exec_mode=ExecMode(row["exec_mode"]),
        )
