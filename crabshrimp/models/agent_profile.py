from enum import Enum
from pydantic import BaseModel


class RoleType(str, Enum):
    planner = "Planner"
    executor = "Executor"
    critic = "Critic"
    verifier = "Verifier"
    summarizer = "Summarizer"


class ContextMode(str, Enum):
    shared = "shared"      # 可看到完整历史输出（默认）
    isolated = "isolated"  # 只看到当前子任务 + 紧邻上一步输出，防止锚定偏差


class WorkspaceMode(str, Enum):
    none = "none"          # 无文件系统隔离（默认）
    scoped = "scoped"      # 拥有独立目录 /tmp/crabshrimp/<task_id>/<agent_id>/


class ExecMode(str, Enum):
    local = "local"           # 不实际执行命令（默认，纯推理角色）
    subprocess = "subprocess"  # asyncio 子进程，工作目录隔离
    docker = "docker"          # Docker 容器（v0.2 预留）


class AgentProfile(BaseModel):
    agent_id: str
    role: RoleType
    system_prompt: str
    contribution_score: float = 1.0
    # 隔离配置（角色级默认值，在 registry.seed_defaults 中按角色设定）
    context_mode: ContextMode = ContextMode.shared
    workspace_mode: WorkspaceMode = WorkspaceMode.none
    exec_mode: ExecMode = ExecMode.local
