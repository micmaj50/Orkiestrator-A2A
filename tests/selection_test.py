import pytest
from operator import attrgetter
from context.context_selection import FOOD_AGENT_SELECTION, GAS_AGENT_SELECTION, PARKING_AGENT_SELECTION, ContextKey
from contracts.agent_request import resolve_agent_context
from context.car import VehicleProfile, VehicleTelemetry, CarContext
from common.fuel import FuelType
from common.location import Coordinates
from datetime import datetime
from contracts.agent_request import AgentContext
from context.context_selection import ContextSelection

"""Simple testing the output of resolve_agent_context function"""

vp = VehicleProfile(fuel_type=FuelType.PETROL_95,
                    tank_capacity=40.0)
vt = VehicleTelemetry(current_location=Coordinates(latitude=1.0, longitude=2.0),
                      remaining_range_km=30.0,
                      observed_at=datetime(2026, 10, 31, 20, 30, 0))

car_context = CarContext(
    profile=vp,
    telemetry=vt)

EXPECTED_VALUES = vp.model_dump(mode='json') | vt.model_dump(mode='json')

@pytest.mark.parametrize("context_key", list(ContextKey))
def test_context_keys(context_key):
    key_selection = resolve_agent_context(car_context=car_context, selection=ContextSelection(fields=[context_key]))
    result = key_selection.model_dump(mode='json')

    target_field = context_key.rsplit(".", maxsplit=1)[-1]
    assert result[target_field] == EXPECTED_VALUES[target_field]

def test_food_agent_selection():
    food_agent_selection = resolve_agent_context(car_context=car_context, selection=FOOD_AGENT_SELECTION)
    result = food_agent_selection.model_dump(mode='json')

    assert result['fuel_type'] is None
    assert result['tank_capacity'] is None
    assert result['remaining_range_km'] is None
    assert result['current_location'] == {
        'latitude': 1.0,
        'longitude': 2.0
    }
    assert result['observed_at'] == '2026-10-31T20:30:00'

def test_gas_agent_selection():
    gas_agent_selection = resolve_agent_context(car_context=car_context, selection=GAS_AGENT_SELECTION)
    result = gas_agent_selection.model_dump(mode='json')

    assert result['fuel_type'] == 'petrol_95'
    assert result['tank_capacity'] is None
    assert result['remaining_range_km'] == 30.0
    assert result['current_location'] == {
        'latitude': 1.0,
        'longitude': 2.0
    }
    assert result['observed_at'] is None

def test_parking_agent_selection():
    parking_agent_selection = resolve_agent_context(car_context=car_context, selection=PARKING_AGENT_SELECTION)
    result = parking_agent_selection.model_dump(mode='json')

    assert result['fuel_type'] is None
    assert result['tank_capacity'] is None
    assert result['remaining_range_km'] is None
    assert result['current_location'] == {
        'latitude': 1.0,
        'longitude': 2.0
    }
    assert result['observed_at'] == '2026-10-31T20:30:00'