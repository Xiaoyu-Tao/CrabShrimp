from crabshrimp.agents.base import BaseAgent


class ExecutorAgent(BaseAgent):
    async def think(self, input_text: str) -> str:
        messages = [{"role": "user", "content": input_text}]
        return await self.llm_client.complete(
            messages, system_prompt=self.profile.system_prompt
        )

    async def act(self, task_context: dict) -> dict:
        subtask = task_context.get("subtask", task_context.get("task_description", ""))
        workspace_hint = (
            f"\n[Workspace: {self.workspace_dir}]"
            if self.workspace_dir
            else ""
        )
        prompt = (
            f"Subtask: {subtask}{workspace_hint}\n\n"
            "Execute this subtask step by step. Show your reasoning, then provide "
            "your final output clearly labeled as 'RESULT:'."
        )
        reasoning = await self.think(prompt)
        output = reasoning
        if self.workspace_dir:
            output += f"\n\n[Workspace: {self.workspace_dir}]"
        return {
            "reasoning": reasoning,
            "output": output,
            "result": "success",
        }
