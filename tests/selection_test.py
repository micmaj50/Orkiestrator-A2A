import pytest
from context.context_selection import ContextKey
from contracts.agent_request import resolve_agent_context
from context.car import VehicleProfile, VehicleTelemetry, CarContext
from context.context_groups import CONTEXT_GROUPS
from common.fuel import FuelType
from common.location import Coordinates
from common.tire_pressure import TirePressure
from datetime import datetime
from context.context_selection import ContextSelection

"""Simple testing the output of resolve_agent_context function"""

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

EXPECTED_VALUES = vp.model_dump(mode='json') | vt.model_dump(mode='json')

@pytest.mark.parametrize("context_key", list(ContextKey))
def test_context_keys(context_key):
    key_selection = resolve_agent_context(car_context=car_context, selection=ContextSelection(fields=[context_key]))
    result = key_selection.model_dump(mode='json')

    target_field = context_key.rsplit(".", maxsplit=1)[-1]
    assert result[target_field] == EXPECTED_VALUES[target_field]

@pytest.mark.parametrize("context_group", CONTEXT_GROUPS)
def test_context_groups(context_group):
    key_selection = resolve_agent_context(car_context=car_context, selection=context_group.context)
    result = key_selection.model_dump(mode='json')

    target_fields = [val.rsplit(".", maxsplit=1)[-1] for val in context_group.context.fields]
    expected = {
        name: value if name in target_fields else None
        for name, value in EXPECTED_VALUES.items()
        }

    assert result == expected
