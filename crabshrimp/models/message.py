from enum import Enum
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    propose = "propose"
    critique = "critique"
    vote = "vote"
    result = "result"
    request_meeting = "request_meeting"


class Message(BaseModel):
    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to: str  # agent_id 或 "broadcast"
    type: MessageType
    content: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    task_id: str
    step_id: str
