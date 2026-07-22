from enum import Enum

from typing import Annotated, Sequence
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages


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
    # `user_input` and `tasks` are per-turn channels: each invocation overwrites
    # them (the executor passes a fresh user_input and an empty tasks list).
    # `messages` accumulates across turns via the add_messages reducer, so when
    # the graph is compiled with a checkpointer keyed by the A2A context_id it
    # becomes the persistent conversation memory shared between turns.
    user_input: HumanMessage
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list)

    tasks: list[Task] = Field(default_factory=list)