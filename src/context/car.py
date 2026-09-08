from enum import StrEnum
from typing import Literal
from datetime import datetime
from pydantic import BaseModel, Field

from common.fuel import FuelType
from common.location import Coordinates
from common.tire_pressure import TirePressure
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
    tank_capacity: float = Field(ge=0)


class VehicleTelemetry(ConfiguredBaseModel):
    """Current, frequently changing vehicle data.
    
    TODO: Decide which live values should be exposed.
    Possible fields:
    - speed;
    - fuel or battery level;
    - current fuel or energy consumption.

    """
    current_location: Coordinates
    remaining_range_km: float | None = Field(default=None, ge=0)

    tire_pressure: TirePressure | None = Field(default=None)
    speed_kmh: float | None = Field(default=None, ge=0)
    observed_at: datetime

    cabin_temperature_c: float | None = Field(default=None)
    outside_temperature_c: float | None = Field(default=None)
    
    ignition_state: Literal["OFF", "ACC", "ON", "STARTING"] | None = Field(default=None)
    odometer_km: float | None = Field(default=None, ge=0)

class CarContext(ConfiguredBaseModel):
    """Vehicle information available to the orchestrator"""

    profile: VehicleProfile
    telemetry: VehicleTelemetry

def create_mock_car(
        current_location = Coordinates(latitude=53.4289, longitude=14.5530),
        remaining_range_km = 100.0,
        observed_at = datetime.now(),
) -> CarContext:
    vp = VehicleProfile(fuel_type=FuelType.PETROL_95,
                        tank_capacity=40.0)
    vt = VehicleTelemetry(current_location=current_location,
                        remaining_range_km=remaining_range_km,
                        tire_pressure=TirePressure(
                            front_left=30,
                            front_right=30,
                            rear_left=30,
                            rear_right=30,
                            unit='psi'
                        ),
                        speed_kmh=60,
                        observed_at=observed_at,
                        cabin_temperature_c=20,
                        outside_temperature_c=30,
                        ignition_state='ON',
                        odometer_km=123456.7)

    car_context = CarContext(
        profile=vp,
        telemetry=vt)

    return car_context