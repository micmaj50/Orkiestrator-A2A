from context.context_selection import FOOD_AGENT_SELECTION, GAS_AGENT_SELECTION, PARKING_AGENT_SELECTION
from contracts.agent_request import resolve_agent_context
from context.car import VehicleProfile, VehicleTelemetry, CarContext
from common.fuel import FuelType
from common.location import Coordinates
from datetime import datetime
from contracts.agent_request import AgentContext

"""Simple testing the output of resolve_agent_context function"""

vp = VehicleProfile(fuel_type=FuelType.PETROL_95,
                    tank_capacity=40.0)
vt = VehicleTelemetry(current_location=Coordinates(latitude=1.0, longitude=2.0),
                      remaining_range_km=30.0,
                      observed_at=datetime.now())

car_context = CarContext(
    profile=vp,
    telemetry=vt)

food_agent_selection = resolve_agent_context(car_context=car_context, selection=FOOD_AGENT_SELECTION)
print(food_agent_selection.model_dump(mode='json'))
"""Expected result for food agent:
{   'fuel_type': None,
    'tank_capacity': None,
    'current_location': {
        'latitude': 1.0,
        'longitude': 2.0
        },
    'remaining_range_km': None,
    'observed_at': {current date}
    }
"""
gas_agent_selection = resolve_agent_context(car_context=car_context, selection=GAS_AGENT_SELECTION)
print(gas_agent_selection.model_dump(mode='json'))
"""Expected result for food agent:
{   'fuel_type': 'petrol_95',
    'tank_capacity': None,
    'current_location': {
        'latitude': 1.0,
        'longitude': 2.0
        },
    'remaining_range_km': 30.0,
    'observed_at': None
    }
"""
parking_agent_selection = resolve_agent_context(car_context=car_context, selection=PARKING_AGENT_SELECTION)
print(parking_agent_selection.model_dump(mode='json'))
"""Expected result for parking agent:
{   'fuel_type': None,
    'tank_capacity': None,
    'current_location': {
        'latitude': 1.0,
        'longitude': 2.0
        },
    'remaining_range_km': None,
    'observed_at': {current date}
    }
"""