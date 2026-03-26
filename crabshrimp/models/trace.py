from datetime import datetime, timezone
from typing import List, Literal
import uuid
from pydantic import BaseModel, Field


class Interaction(BaseModel):
    agent_id: str
    reaction: Literal["agree", "disagree", "supplement"]
    content: str


class TraceStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    agent_id: str
    input: str
    reasoning: str
    output: str
    interactions: List[Interaction] = Field(default_factory=list)
    result: Literal["success", "failure", "rejected"]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
