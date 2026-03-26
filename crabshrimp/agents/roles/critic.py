from crabshrimp.agents.base import BaseAgent


class CriticAgent(BaseAgent):
    async def think(self, input_text: str) -> str:
        messages = [{"role": "user", "content": input_text}]
        return await self.llm_client.complete(
            messages, system_prompt=self.profile.system_prompt
        )

    async def act(self, task_context: dict) -> dict:
        content_to_review = task_context.get("output_to_review", "")
        prompt = (
            f"Review the following output critically:\n\n{content_to_review}\n\n"
            "Identify at least 2 specific flaws, risks, or missing elements. "
            "Be constructive but rigorous. Label each flaw clearly.\n\n"
            "End your review with exactly one of:\n"
            "QUALITY: ACCEPTABLE  — output meets minimum standards despite flaws\n"
            "QUALITY: REJECTED    — output has fundamental issues requiring rework"
        )
        reasoning = await self.think(prompt)
        rejected = "QUALITY: REJECTED" in reasoning.upper()
        return {
            "reasoning": reasoning,
            "output": reasoning,
            "result": "rejected" if rejected else "success",
        }
