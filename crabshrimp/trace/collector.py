from typing import List
from crabshrimp.models.trace import Interaction, TraceStep
from .writer import TraceWriter


class TraceCollector:
    def __init__(self, task_id: str, writer: TraceWriter, enabled: bool = True):
        self._task_id = task_id
        self._writer = writer
        self._steps: List[TraceStep] = []
        self._enabled = enabled

    def record_step(
        self,
        agent_id: str,
        input_text: str,
        reasoning: str,
        output: str,
        interactions: List[Interaction],
        result: str,
    ) -> TraceStep:
        step = TraceStep(
            task_id=self._task_id,
            agent_id=agent_id,
            input=input_text,
            reasoning=reasoning,
            output=output,
            interactions=interactions,
            result=result,
        )
        self._steps.append(step)
        if self._enabled:
            self._writer.write(step)
        return step

    def get_all_steps(self) -> List[TraceStep]:
        return list(self._steps)
