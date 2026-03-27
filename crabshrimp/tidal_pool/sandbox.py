import asyncio
from abc import ABC, abstractmethod
from pathlib import Path


class SandboxInterface(ABC):
    """沙箱执行环境抽象接口。"""

    @abstractmethod
    async def execute(self, command: str, timeout: float = 30.0) -> dict:
        """执行命令，返回 {stdout, stderr, exit_code}。"""

    @abstractmethod
    async def cleanup(self) -> None:
        """释放沙箱资源。"""


class LocalSandbox(SandboxInterface):
    """无隔离占位实现：不实际执行命令，供纯推理角色使用。"""

    async def execute(self, command: str, timeout: float = 30.0) -> dict:
        return {
            "stdout": f"[LocalSandbox] command received (not executed): {command}",
            "stderr": "",
            "exit_code": 0,
        }

    async def cleanup(self) -> None:
        pass


class SubprocessSandbox(SandboxInterface):
    """
    子进程隔离沙箱：通过 asyncio 子进程执行命令，工作目录限定在 workspace_dir。

    适用于 Executor 角色需要运行代码的场景。
    不提供内核级别的资源隔离，更强的隔离需 DockerSandbox（v0.5）。
    """

    def __init__(self, workspace_dir: Path):
        self._workspace = workspace_dir

    async def execute(self, command: str, timeout: float = 30.0) -> dict:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workspace),
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout}s.",
                    "exit_code": -1,
                }
            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "exit_code": proc.returncode,
            }
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}

    async def cleanup(self) -> None:
        pass  # 目录生命周期由 WorkspaceManager 统一管理


class DockerSandbox(SandboxInterface):
    """Docker 容器隔离沙箱（v0.5 预留接口）。"""

    async def execute(self, command: str, timeout: float = 30.0) -> dict:
        raise NotImplementedError("DockerSandbox is planned for v0.5.")

    async def cleanup(self) -> None:
        raise NotImplementedError("DockerSandbox is planned for v0.5.")
