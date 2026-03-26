import tempfile
from pathlib import Path

from crabshrimp.config import CrabShrimpConfig
from crabshrimp.runtime.runner import TaskRunner
from crabshrimp.trace.collector import TraceCollector
from crabshrimp.trace.writer import NullTraceWriter, TraceWriter


def test_trace_collector_keeps_steps_when_persistence_disabled():
    collector = TraceCollector(task_id="task-1", writer=NullTraceWriter(), enabled=False)
    collector.record_step(
        agent_id="executor-001",
        input_text="x",
        reasoning="r",
        output="o",
        interactions=[],
        result="success",
    )

    assert len(collector.get_all_steps()) == 1


def test_task_runner_disables_trace_file_but_preserves_steps(monkeypatch):
    class StubLLM:
        async def complete(self, messages, system_prompt=None, **kwargs):
            content = messages[0]["content"] if messages else ""
            if system_prompt and "task classifier" in system_prompt:
                return "analysis"
            if system_prompt and "JSON execution plan" in system_prompt:
                return (
                    '[{"step_id": 1, "description": "Do work", "role": "Executor", '
                    '"is_critical_node": false}, {"step_id": 2, "description": "Summarize", '
                    '"role": "Summarizer", "is_critical_node": false}]'
                )
            if content.startswith("Subtask: Do work"):
                return "RESULT: work complete"
            if content.startswith("Synthesize the following outputs"):
                return "FINAL: summarized"
            raise AssertionError(f"Unexpected prompt: {content}")

        def count_tokens(self, text):
            return len(text)

    monkeypatch.setattr("crabshrimp.runtime.runner.LiteLLMClient", lambda **kwargs: StubLLM())

    with tempfile.TemporaryDirectory() as tmpdir:
        trace_dir = Path(tmpdir) / "traces"
        db_path = Path(tmpdir) / "crabshrimp.db"
        config = CrabShrimpConfig(
            trace_enabled=False,
            skill_extraction_enabled=False,
            skill_injection_enabled=False,
            coral_meeting_enabled=False,
            trace_dir=str(trace_dir),
            db_path=str(db_path),
        )

        result = TaskRunner(config).run("demo task")

        assert result["steps_count"] == 2
        assert "trace_path" not in result
        assert not trace_dir.exists()
