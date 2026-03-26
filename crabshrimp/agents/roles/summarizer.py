from crabshrimp.agents.base import BaseAgent


class SummarizerAgent(BaseAgent):
    async def think(self, input_text: str) -> str:
        messages = [{"role": "user", "content": input_text}]
        return await self.llm_client.complete(
            messages, system_prompt=self.profile.system_prompt
        )

    async def act(self, task_context: dict) -> dict:
        outputs = task_context.get("outputs_to_summarize", [])
        combined = "\n\n---\n\n".join(
            f"[{item.get('agent_id', 'unknown')}]:\n{item.get('output', '')}"
            for item in outputs
        )
        prompt = (
            f"Synthesize the following outputs from multiple agents into a single "
            f"coherent final answer:\n\n{combined}\n\n"
            "Resolve any contradictions, integrate the key insights, and present "
            "a clear, concise final conclusion."
        )
        reasoning = await self.think(prompt)
        return {
            "reasoning": reasoning,
            "output": reasoning,
            "result": "success",
        }
