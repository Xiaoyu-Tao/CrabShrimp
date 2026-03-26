import asyncio
import json
import tempfile

from crabshrimp.agents.factory import AgentFactory
from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.communication.blackboard import AsyncBlackboard
from crabshrimp.config import CrabShrimpConfig
from crabshrimp.coral_meeting.meeting import CoralMeeting
from crabshrimp.dragon_king.orchestrator import DragonKing
from crabshrimp.tidal_pool.resource_guard import ResourceGuard
from crabshrimp.trace.collector import TraceCollector
from crabshrimp.trace.writer import TraceWriter


class RecordingLLM:
    def __init__(self):
        self.summarizer_prompts = []

    async def complete(self, messages, system_prompt=None, **kwargs):
        content = messages[0]["content"] if messages else ""
        if system_prompt and "task classifier" in system_prompt:
            return "writing"
        if system_prompt and "JSON execution plan" in system_prompt:
            return json.dumps([
                {
                    "step_id": 1,
                    "description": "Draft answer",
                    "role": "Executor",
                    "is_critical_node": False,
                },
                {
                    "step_id": 2,
                    "description": "Summarize results",
                    "role": "Summarizer",
                    "is_critical_node": True,
                },
            ])
        if content.startswith("Subtask: Draft answer"):
            return "RESULT: executor-output"
        if content.startswith("Synthesize the following outputs"):
            self.summarizer_prompts.append(content)
            return f"SUMMARY_CALL_{len(self.summarizer_prompts)}"
        if content.startswith("Review the following output critically"):
            return "Flaw 1\nFlaw 2"
        if content.startswith("Independently verify the correctness"):
            return "VERIFIED"
        if "Which position is best?" in content:
            return "MEETING-CONSENSUS"
        raise AssertionError(f"Unexpected prompt: {content}")

    def count_tokens(self, text):
        return len(text)


def test_critical_summarizer_step_runs_before_meeting():
    async def run_case():
        llm = RecordingLLM()
        registry = AgentRegistry()
        registry.seed_defaults()

        with tempfile.NamedTemporaryFile() as trace_file:
            with TraceWriter(trace_file.name) as writer:
                collector = TraceCollector(task_id="task-1", writer=writer)
                dragon_king = DragonKing(
                    llm_client=llm,
                    registry=registry,
                    factory=AgentFactory(llm),
                    coral_meeting=CoralMeeting(llm, collector),
                    resource_guard=ResourceGuard(step_limit=10, token_budget=10_000),
                    trace_collector=collector,
                    blackboard=AsyncBlackboard(),
                    config=CrabShrimpConfig(),
                )
                result = await dragon_king.run_task("task-1", "demo task")
                return result, collector.get_all_steps(), llm.summarizer_prompts

    result, steps, summarizer_prompts = asyncio.run(run_case())

    assert result["final_output"] == "MEETING-CONSENSUS"
    assert [step.agent_id for step in steps] == [
        "executor-001",
        "summarizer-001",
        "coral-meeting",
    ]
    assert "executor-output" in summarizer_prompts[0]
