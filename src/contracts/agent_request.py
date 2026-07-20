from enum import StrEnum
from operator import attrgetter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from common.location import Coordinates
from common.model_config import ConfiguredBaseModel
from context.car import CarContext


class ContextKey(StrEnum):
    # if we ever add SystemContext class with a `car` field inside it, the path must start with `car`
    # currently, our AgentRequest and resolver accept `CarContex`
    CURRENT_LOCATION = "telemetry.current_location"


class ContextSelection(ConfiguredBaseModel):
    fields: list[ContextKey] = Field(default_factory=list)


class AgentContext(ConfiguredBaseModel):
    current_location: Coordinates | None = None


def resolve_agent_context(
        car_context: CarContext,
        selection: ContextSelection
        ) -> AgentContext:
    values: dict[str, Any] = {}

    for context_key in selection.fields:
        source_path = context_key.value
        target_field = source_path.rsplit(".", maxsplit=1)[-1]

        values[target_field] = attrgetter(source_path)(car_context)

    return AgentContext.model_validate(values)


class AgentRequest(ConfiguredBaseModel):
    """Work delegated by the orchestrator to a sub-agent
    `user_query` preserves the original input. (TODO: does a sub-agent need to know about it?)

    `task` describes the specific work assigned to the receiving agent by the orchestrator.

    TODO: Decide how system context should be attached to agent requests.
    Possible approaches include optional shared fields, agent-specific 
    contracts, or dynamically selected typed context items.

    `parameters`?
    """

    user_query: str
    task: str
    
    context: AgentContext = Field(default_factory=AgentContext)

# def serialize_agent_input - ?
# create seelction, run the resolver, contstruct a request, contruct a payload, print it
# the test below is probably outdated, I'm not sure

# Test
# llm_output = {
#         "task": "Find restaurants near the car",
#         "required_context": [
#             "car.telemetry.current_location"
#             ],
#         }
#
# request = AgentRequest(
#         user_query="test"
#         task="test"
#         context=resolve_agent_context()
#         )
#
