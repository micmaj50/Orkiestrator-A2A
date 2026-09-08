from datetime import datetime
from operator import attrgetter
from typing import Any, Literal, Self

from pydantic import Field

from common.fuel import FuelType
from common.location import Coordinates
from common.model_config import ConfiguredBaseModel
from common.tire_pressure import TirePressure
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

    @classmethod
    def select_from_car_context(
        cls,
        car_context: CarContext,
        selection: ContextSelection
        ) -> Self:
        values: dict[str, Any] = {}

        for context_key in selection.fields:
            source_path = context_key.value
            target_field = source_path.rsplit(".", maxsplit=1)[-1]

            values[target_field] = attrgetter(source_path)(car_context)

        return cls.model_validate(values)
    
    def get_context_for_query(self) -> str:
        context = self.model_dump_json(exclude_none=True)
        return f" Current car metrics: {context}"