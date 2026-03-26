"""Phase 1 验证：数据模型可实例化和序列化。"""
from crabshrimp.models.message import Message, MessageType
from crabshrimp.models.trace import TraceStep, Interaction
from crabshrimp.models.agent_profile import AgentProfile, RoleType


def test_message_creation():
    msg = Message(
        from_agent="agent-1",
        to="agent-2",
        type=MessageType.propose,
        content="Hello",
        task_id="task-001",
        step_id="step-001",
    )
    assert msg.msg_id is not None
    assert msg.type == MessageType.propose
    data = msg.model_dump_json()
    assert "propose" in data


def test_trace_step_creation():
    step = TraceStep(
        task_id="task-001",
        agent_id="executor-001",
        input="do something",
        reasoning="I think...",
        output="done",
        interactions=[Interaction(agent_id="critic-001", reaction="agree", content="good")],
        result="success",
    )
    assert step.step_id is not None
    assert step.result == "success"
    assert len(step.interactions) == 1


def test_agent_profile_creation():
    profile = AgentProfile(
        agent_id="planner-001",
        role=RoleType.planner,
        system_prompt="You are a planner.",
    )
    assert profile.contribution_score == 1.0
    assert profile.role == RoleType.planner
