from enum import Enum

from typing import Annotated, Sequence
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages

from context.car import CarContext


class TaskStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    id: int
    query: str | None = None
    status: TaskStatus = TaskStatus.IN_PROGRESS
    assigned_agent: str | None = None
    result: str | None = None

class GraphState(BaseModel):
    user_input: HumanMessage
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list)

    tasks: list[Task] = Field(default_factory=list)

    # Vehicle context (profile + live telemetry) made available to the whole graph.
    # The orchestrator forwards a per-agent subset of this to each sub-agent.
    car: CarContext | None = None