from enum import StrEnum

from datetime import datetime

from pydantic import BaseModel, Field

from common.fuel import FuelType
from common.location import Coordinates
from common.model_config import ConfiguredBaseModel


class VehicleProfile(ConfiguredBaseModel):
    """Relatively stable vehicle properties.

    Kept separate from telemetry because these values are not expected to change.
    
    TODO: Decide which properties are required by current future and future agents.
    Possible fields:
    - vehicle type;
    - tank or battery capacity
    - average fuel or energy consumption.
    """

    fuel_type: FuelType


class VehicleTelemetry(ConfiguredBaseModel):
    """Current, frequently changing vehicle data.
    
    TODO: Decide which live values should be exposed.
    Possible fields:
    - speed;
    - fuel or battery level;
    - current fuel or energy consumption.

    TODO: Decide whether telemetry needs an `observed_at` timestamp for historical telemetry.
    """
    current_location: Coordinates
    remaining_range_km: float | None = Field(default=None, ge=0)
    # observed_at: datetime


class CarContext(ConfiguredBaseModel):
    """Vehicle information available to the orchestrator

    TODO: Decide whether all data should be forwarded to a particular agent 
    and if not, how will we manage it.

    TODO: Decide whether route-related information belongs here or in a separate trip context.
    """
    profile: VehicleProfile
    telemetry: VehicleTelemetry
