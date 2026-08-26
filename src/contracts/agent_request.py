from operator import attrgetter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Literal

from common.fuel import FuelType
from common.location import Coordinates
from common.tire_pressure import TirePressure
from common.model_config import ConfiguredBaseModel
from context.car import CarContext
from context.context_selection import ContextSelection


class AgentContext(ConfiguredBaseModel):
    fuel_type: FuelType | None = None
    tank_capacity: float | None = Field(default=None, ge=0)

    current_location: Coordinates | None = None
    remaining_range_km: float | None = Field(default=None, ge=0)
    tire_pressure: TirePressure | None = Field(default=None)
    speed_kmh: float | None = Field(default=None, ge=0)
    observed_at: datetime | None = None

    cabin_temperature_c: float | None = Field(default=None)
    outside_temperature_c: float | None = Field(default=None)
    
    ignition_state: Literal["OFF", "ACC", "ON", "STARTING"] | None = Field(default=None)
    odometer_km: float | None = Field(default=None, ge=0)


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
    """Class that will be mosty used when LLM is implemented for determaining the needed context"""

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