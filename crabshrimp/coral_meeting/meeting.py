from typing import TYPE_CHECKING, List, Optional, Tuple
from crabshrimp.agents.base import BaseAgent
from crabshrimp.communication.p2p import SyncP2P
from crabshrimp.llm.base import BaseLLMClient
from crabshrimp.models.message import Message
from crabshrimp.models.trace import Interaction
from crabshrimp.trace.collector import TraceCollector

if TYPE_CHECKING:
    from crabshrimp.db.meeting_repo import MeetingRepository

_ARBITRATE_PROMPT = """You are a neutral arbitrator. Given multiple positions on a topic,
select the best one and explain why in 2-3 sentences. Be decisive."""


class CoralMeeting:
    """
    Coral-Meeting 协同决策引擎。
    6 步会议流程：陈述 → 交叉反思(P2P) → 立场修订 → 加权投票 → 裁决 → 记录

    convene() 返回 (consensus_text, winner_agent_id)
      - winner_agent_id: 立场被采纳的 Agent ID；LLM 仲裁时为 None
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        trace_collector: TraceCollector,
        meeting_repo: Optional["MeetingRepository"] = None,
    ):
        self._llm = llm_client
        self._trace = trace_collector
        self._meeting_repo = meeting_repo

    async def convene(
        self,
        task_id: str,
        step_id: str,
        topic: str,
        participants: List[BaseAgent],
        context: str = "",
        shared_outputs: list | None = None,
    ) -> Tuple[str, Optional[str]]:
        """
        返回 (consensus, winner_agent_id)
        """
        if not participants:
            return context, None

        print(f"  [CoralMeeting] Topic: {topic}")
        print(f"  [CoralMeeting] Participants: {[a.role for a in participants]}")

        # Step 1：各方陈述立场
        positions = {}
        for agent in participants:
            result = await agent.act({
                "task_description": topic,
                "subtask": f"State your position on: {topic}\nContext: {context}",
                "output_to_review": context,
                "outputs_to_summarize": shared_outputs or [],
            })
            positions[agent.agent_id] = result.get("output", "")
            print(f"  [Step1] {agent.role}: {positions[agent.agent_id][:80]}...")

        # Step 2：交叉反思（使用 SyncP2P 将批评消息投递到被批评方收件箱）
        p2p = SyncP2P()
        critiques = {}
        for agent in participants:
            others = {
                aid: pos for aid, pos in positions.items() if aid != agent.agent_id
            }
            others_text = "\n".join(f"- {aid}: {pos}" for aid, pos in others.items())
            result = await agent.act({
                "task_description": topic,
                "subtask": f"Critique the following positions (find at least 2 flaws each):\n{others_text}",
                "output_to_review": others_text,
                "outputs_to_summarize": [],
            })
            critique_text = result.get("output", "")
            critiques[agent.agent_id] = critique_text

            # 把批评消息投递给每位被批评方（P2P 直发）
            for target_id in others:
                await p2p.send(
                    to_agent_id=target_id,
                    message=Message(
                        from_agent=agent.agent_id,
                        to=target_id,
                        type="critique",
                        content=critique_text[:400],
                        task_id=task_id,
                        step_id=step_id,
                    ),
                )

        # 每个参与者接收发给自己的批评（非阻塞：有多少收多少）
        received: dict[str, list[str]] = {a.agent_id: [] for a in participants}
        for agent in participants:
            n_expected = len(participants) - 1
            for _ in range(n_expected):
                try:
                    msg = await p2p.receive(agent.agent_id, timeout=0.05)
                    received[agent.agent_id].append(f"[from {msg.from_agent}] {msg.content}")
                except Exception:
                    break

        # Step 2.5：立场修订（收到批评后，各方可选择更新自己的立场）
        for agent in participants:
            inbox = received.get(agent.agent_id, [])
            if not inbox:
                continue
            critiques_received = "\n".join(inbox)
            revision_result = await agent.act({
                "task_description": topic,
                "subtask": (
                    f"You stated the following position:\n{positions[agent.agent_id]}\n\n"
                    f"You received these critiques:\n{critiques_received}\n\n"
                    "Revise your position if the critiques are valid. "
                    "If your original position is sound, restate it clearly. "
                    "Output only your final revised position."
                ),
                "output_to_review": positions[agent.agent_id],
                "outputs_to_summarize": [],
            })
            revised = revision_result.get("output", "").strip()
            if revised:
                positions[agent.agent_id] = revised

        # Step 3：加权投票（基于修订后的立场）
        votes: dict = {}
        for agent in participants:
            votes[agent.agent_id] = {
                "position": positions[agent.agent_id],
                "weight": agent.profile.contribution_score,
            }

        # Step 4：裁决
        sorted_by_weight = sorted(votes.items(), key=lambda x: x[1]["weight"], reverse=True)
        top_agent_id, top_vote = sorted_by_weight[0]
        consensus = top_vote["position"]
        winner_agent_id: Optional[str] = top_agent_id

        if len(sorted_by_weight) > 1:
            second_weight = sorted_by_weight[1][1]["weight"]
            if abs(top_vote["weight"] - second_weight) < 0.01:
                # 平票 → LLM 仲裁，无明确 winner
                consensus = await self._arbitrate(topic, positions)
                winner_agent_id = None

        print(f"  [CoralMeeting] Consensus reached ✓  winner={winner_agent_id or 'arbitrated'}")

        # Step 5：记录 Trace + DB
        interactions = [
            Interaction(agent_id=aid, reaction="supplement", content=pos[:200])
            for aid, pos in positions.items()
        ]
        # 将 P2P 收到的批评也记录到 Interaction 中
        for agent_id, msgs in received.items():
            for msg_text in msgs:
                interactions.append(
                    Interaction(agent_id=agent_id, reaction="disagree", content=msg_text[:200])
                )
        self._trace.record_step(
            agent_id="coral-meeting",
            input_text=topic,
            reasoning=str(critiques),
            output=consensus,
            interactions=interactions,
            result="success",
        )
        if self._meeting_repo:
            self._meeting_repo.save_outcome(
                task_id=task_id,
                step_id=step_id,
                winner_agent_id=winner_agent_id,
                topic=topic,
            )

        return consensus, winner_agent_id

    async def _arbitrate(self, topic: str, positions: dict) -> str:
        positions_text = "\n".join(
            f"Position {i+1}: {pos}" for i, pos in enumerate(positions.values())
        )
        messages = [{
            "role": "user",
            "content": f"Topic: {topic}\n\nPositions:\n{positions_text}\n\nWhich position is best?",
        }]
        return await self._llm.complete(messages, system_prompt=_ARBITRATE_PROMPT)
