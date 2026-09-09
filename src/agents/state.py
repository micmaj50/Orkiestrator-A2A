from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from contracts.agent_request import AgentContext


class WorkItemStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    NEED_CONTEXT = "need_context"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkItem(BaseModel):
    id: int
    query: str | None = None
    status: WorkItemStatus = WorkItemStatus.IN_PROGRESS
    assigned_agent: str | None = None
    result: str | None = None
    context: AgentContext | None = None

class GraphState(BaseModel):
    user_input: HumanMessage
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list)

    tasks: list[WorkItem] = Field(default_factory=list)
    tasks_dropped: bool = False

