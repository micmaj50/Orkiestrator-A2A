import json
from datetime import datetime

import pytest
from dotenv import load_dotenv

from agents.orchestrator.llm import Llm
from common.fuel import FuelType
from common.location import Coordinates
from common.tire_pressure import TirePressure
from context.car import CarContext, VehicleProfile, VehicleTelemetry
from context.context_groups import CONTEXT_GROUPS
from contracts.agent_request import AgentRequest

load_dotenv()

vp = VehicleProfile(fuel_type=FuelType.PETROL_95,
                    tank_capacity=40.0)
vt = VehicleTelemetry(current_location=Coordinates(latitude=1.0, longitude=2.0),
                      remaining_range_km=30.0,
                      tire_pressure=TirePressure(
                          front_left=30,
                          front_right=30,
                          rear_left=30,
                          rear_right=30,
                          unit='psi'
                      ),
                      speed_kmh=60,
                      observed_at=datetime(2026, 10, 31, 20, 30, 0),
                      cabin_temperature_c=20,
                      outside_temperature_c=30,
                      ignition_state='ON',
                      odometer_km=123456.7)

car_context = CarContext(
    profile=vp,
    telemetry=vt)

query = "find a gas station"
number_of_groups = 3

@pytest.mark.parametrize("task", [
    "find a gas station",
    "temperature"
])
def test_agent_request(task):
    request = AgentRequest(user_input=query, task=task, number_of_groups=number_of_groups)

    result = request.select_context(car_context=car_context, llm=Llm())
    print(f"\n\n====Task: {task}===")
    print(result)
