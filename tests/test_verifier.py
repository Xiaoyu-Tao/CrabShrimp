import asyncio
import subprocess
import sys

from crabshrimp.agents.roles.verifier import VerifierAgent
from crabshrimp.models.agent_profile import AgentProfile, RoleType


class StubLLM:
    def __init__(self, response: str):
        self._response = response

    async def complete(self, messages, system_prompt=None, **kwargs):
        return self._response

    def count_tokens(self, text: str) -> int:
        return len(text)


def test_not_verified_maps_to_failure():
    async def run_case():
        agent = VerifierAgent(
            AgentProfile(agent_id="verifier-001", role=RoleType.verifier, system_prompt="x"),
            StubLLM("Conclusion: NOT VERIFIED because evidence is missing."),
        )
        return await agent.act({"output_to_review": "demo"})

    result = asyncio.run(run_case())
    assert result["result"] == "failure"


def test_importing_llm_base_does_not_require_litellm():
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from crabshrimp.llm.base import BaseLLMClient; print(BaseLLMClient.__name__)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "BaseLLMClient"
