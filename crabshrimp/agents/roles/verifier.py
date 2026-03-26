import re

from crabshrimp.agents.base import BaseAgent


class VerifierAgent(BaseAgent):
    async def think(self, input_text: str) -> str:
        messages = [{"role": "user", "content": input_text}]
        return await self.llm_client.complete(
            messages, system_prompt=self.profile.system_prompt
        )

    async def act(self, task_context: dict) -> dict:
        content_to_verify = task_context.get("output_to_review", "")
        prompt = (
            f"Independently verify the correctness of the following:\n\n{content_to_verify}\n\n"
            "Check for logical consistency, factual accuracy, and completeness. "
            "Conclude with VERIFIED or NOT VERIFIED and explain why."
        )
        reasoning = await self.think(prompt)
        upper = reasoning.upper()
        # 先检查 NOT VERIFIED（优先级高），再检查 VERIFIED，避免"VERIFIED"匹配到"NOT VERIFIED"中
        if re.search(r"\bNOT VERIFIED\b", upper):
            verified = False
        elif re.search(r"\bVERIFIED\b", upper):
            verified = True
        else:
            verified = False
        return {
            "reasoning": reasoning,
            "output": reasoning,
            "result": "success" if verified else "failure",
        }
