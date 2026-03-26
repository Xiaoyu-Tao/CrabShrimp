import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    skill_id       TEXT PRIMARY KEY,
    role           TEXT NOT NULL,
    task_category  TEXT NOT NULL,
    content        TEXT NOT NULL,
    source_task_id TEXT,
    usage_count    INTEGER DEFAULT 0,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS role_weights (
    task_category  TEXT NOT NULL,
    role           TEXT NOT NULL,
    agent_id       TEXT NOT NULL,
    wins           INTEGER DEFAULT 0,
    total          INTEGER DEFAULT 0,
    PRIMARY KEY (task_category, role, agent_id)
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id            TEXT PRIMARY KEY,
    role                TEXT NOT NULL,
    system_prompt       TEXT NOT NULL,
    contribution_score  REAL    DEFAULT 1.0,
    context_mode        TEXT    DEFAULT 'shared',
    workspace_mode      TEXT    DEFAULT 'none',
    exec_mode           TEXT    DEFAULT 'local',
    updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS task_records (
    task_id         TEXT PRIMARY KEY,
    description     TEXT,
    category        TEXT,
    stopped_early   INTEGER DEFAULT 0,
    steps_count     INTEGER DEFAULT 0,
    trace_path      TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS meeting_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT    NOT NULL,
    step_id         TEXT    NOT NULL,
    winner_agent_id TEXT,
    topic           TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS prompt_optimizations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    role           TEXT NOT NULL,
    task_category  TEXT NOT NULL,
    patch          TEXT NOT NULL,
    source_task_id TEXT,
    usage_count    INTEGER DEFAULT 0,
    created_at     TEXT
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    """创建（或复用）SQLite 连接，自动初始化 Schema。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn
