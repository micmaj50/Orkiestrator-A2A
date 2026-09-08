from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Self

from pydantic import Field

from common.model_config import ConfiguredBaseModel

if TYPE_CHECKING:
    from context.context_groups import ContextGroup

class ContextKey(StrEnum):
    # if we ever add SystemContext class with a `car` field inside it, the path must start with `car`
    # currently, our AgentRequest and resolver accept `CarContex`
    FUEL_TYPE = "profile.fuel_type"
    TANK_CAPACITY = "profile.tank_capacity"
    CURRENT_LOCATION = "telemetry.current_location"
    REMAINING_RANGE_KM = "telemetry.remaining_range_km"
    TIRE_PRESSURE = "telemetry.tire_pressure"
    SPEED_KMH = "telemetry.speed_kmh"
    OBSERVED_AT = "telemetry.observed_at"
    CABIN_TEMP_C = "telemetry.cabin_temperature_c"
    OUTSIDE_TEMP_C = "telemetry.outside_temperature_c"
    IGNITION_STATE = "telemetry.ignition_state"
    ODOMETER_KM = "telemetry.odometer_km"


class ContextSelection(ConfiguredBaseModel):
    fields: list[ContextKey] = Field(default_factory=list)

    @classmethod
    def from_groups(cls, selected_context: list[ContextGroup]) -> Self:
        combined_fields = list(
            dict.fromkeys(
            field
            for obj in selected_context
            for field in obj.context.fields
            ))

        return cls(fields=combined_fields)
