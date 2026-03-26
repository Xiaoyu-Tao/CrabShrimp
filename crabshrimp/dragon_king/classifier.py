from typing import Literal
from crabshrimp.llm.base import BaseLLMClient

TaskCategory = Literal["code", "analysis", "reasoning", "writing", "general"]

_CLASSIFY_PROMPT = """You are a task classifier. Classify the given task into exactly one category:
- code: software development, debugging, code review, programming
- analysis: data analysis, research, literature review, evaluation
- reasoning: logic puzzles, math, scientific inference, problem solving
- writing: report writing, documentation, summarization, content creation
- general: anything that doesn't fit the above

Reply with ONLY the category name, nothing else."""


class TaskClassifier:
    def __init__(self, llm_client: BaseLLMClient):
        self._llm = llm_client

    async def classify(self, task_description: str) -> TaskCategory:
        messages = [{"role": "user", "content": f"Task: {task_description}"}]
        result = await self._llm.complete(messages, system_prompt=_CLASSIFY_PROMPT)
        category = result.strip().lower()
        valid = {"code", "analysis", "reasoning", "writing", "general"}
        return category if category in valid else "general"
