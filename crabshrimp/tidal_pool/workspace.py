import shutil
from pathlib import Path
from typing import Dict


class WorkspaceManager:
    """
    为需要工作空间隔离的 Agent 分配独立临时目录。

    目录结构：{base_dir}/{task_id}/{agent_id}/
    任务结束后调用 cleanup() 一次性清理整个 task 目录。
    """

    def __init__(self, task_id: str, base_dir: str = "/tmp/crabshrimp"):
        self._task_id = task_id
        self._base = Path(base_dir)
        self._dirs: Dict[str, Path] = {}

    def get_or_create(self, agent_id: str) -> Path:
        """返回 agent 的独立工作目录，不存在则自动创建。"""
        if agent_id not in self._dirs:
            ws = self._base / self._task_id / agent_id
            ws.mkdir(parents=True, exist_ok=True)
            self._dirs[agent_id] = ws
        return self._dirs[agent_id]

    def list_workspaces(self) -> Dict[str, Path]:
        """返回已分配的所有工作空间。"""
        return dict(self._dirs)

    def cleanup(self) -> None:
        """清理当前 task 下的所有工作空间。"""
        task_dir = self._base / self._task_id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
            print(f"[WorkspaceManager] Cleaned up {task_dir}")
        self._dirs.clear()
