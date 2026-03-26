from crabshrimp.agents.base import BaseAgent


class PlannerAgent(BaseAgent):
    async def think(self, input_text: str) -> str:
        messages = [{"role": "user", "content": input_text}]
        return await self.llm_client.complete(
            messages, system_prompt=self.profile.system_prompt
        )

    async def act(self, task_context: dict) -> dict:
        task_desc = task_context.get("task_description", "")
        prompt = (
            f"Task: {task_desc}\n\n"
            "Please analyze this task and produce a structured execution plan. "
            "List each step with: step number, description, responsible role "
            "(Planner/Executor/Critic/Verifier/Summarizer), and whether it is a "
            "critical decision node (yes/no). Output as a numbered list."
        )
        reasoning = await self.think(prompt)
        return {
            "reasoning": reasoning,
            "output": reasoning,
            "result": "success",
        }
