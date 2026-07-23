from enum import StrEnum
from typing import Final

from pydantic import Field
from common.model_config import ConfiguredBaseModel

class ContextKey(StrEnum):
    # if we ever add SystemContext class with a `car` field inside it, the path must start with `car`
    # currently, our AgentRequest and resolver accept `CarContex`
    FUEL_TYPE = "profile.fuel_type"
    TANK_CAPACITY = "PROFILE.tank_capacity"
    CURRENT_LOCATION = "telemetry.current_location"
    REMAINING_RANGE_KM = "telemetry.remaining_range_km"
    OBSERVED_AT = "telemetry.observed_at"


class ContextSelection(ConfiguredBaseModel):
    fields: list[ContextKey] = Field(default_factory=list)


"""Predetermined context for each agent"""
#in AgentSkill could be included in description as " ... needs: {list[ContextKey]}"

FOOD_AGENT_SELECTION: Final = ContextSelection(
    fields=[ContextKey.CURRENT_LOCATION,
            ContextKey.OBSERVED_AT])

GAS_AGENT_SELECTION: Final = ContextSelection(
    fields=[ContextKey.FUEL_TYPE,
            ContextKey.CURRENT_LOCATION,
            ContextKey.REMAINING_RANGE_KM])

PARKING_AGENT_SELECTION: Final = ContextSelection(
    fields=[ContextKey.CURRENT_LOCATION,
            ContextKey.OBSERVED_AT])
