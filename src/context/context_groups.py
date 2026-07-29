from pydantic import Field
from common.model_config import ConfiguredBaseModel
from .context_selection import ContextKey, ContextSelection

class ContextGroup(ConfiguredBaseModel):
    description: str
    context: ContextSelection = Field(default_factory=ContextSelection)


CONTEXT_GROUPS = [
    ContextGroup(
        description="Vehicle location and positioning tracking",
        context=ContextSelection(
            fields=[
                ContextKey.CURRENT_LOCATION,
                ContextKey.SPEED_KMH,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="Finding something to eat, restaurants, and dining",
        context=ContextSelection(
            fields=[
                ContextKey.CURRENT_LOCATION,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="Fuel profile and remaining range metrics",
        context=ContextSelection(
            fields=[
                ContextKey.FUEL_TYPE,
                ContextKey.TANK_CAPACITY,
                ContextKey.REMAINING_RANGE_KM
            ]
        )
    ),
    ContextGroup(
        description="Finding a hairdresser, barber, or grooming services",
        context=ContextSelection(
            fields=[
                ContextKey.CURRENT_LOCATION,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="Distance calculations and range availability",
        context=ContextSelection(
            fields=[
                ContextKey.REMAINING_RANGE_KM,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="Vehicle speed and velocity metrics",
        context=ContextSelection(
            fields=[
                ContextKey.SPEED_KMH,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="General vehicle status and overview metrics",
        context=ContextSelection(
            fields=[
                ContextKey.IGNITION_STATE,
                ContextKey.ODOMETER_KM,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="Tire pressure status and wheel health safety",
        context=ContextSelection(
            fields=[
                ContextKey.TIRE_PRESSURE,
                ContextKey.SPEED_KMH,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="Internal cabin comfort",
        context=ContextSelection(
            fields=[
                ContextKey.CABIN_TEMP_C,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="Commute optimization, engine states, and odometer tracking",
        context=ContextSelection(
            fields=[
                ContextKey.CURRENT_LOCATION,
                ContextKey.ODOMETER_KM,
                ContextKey.IGNITION_STATE,
                ContextKey.OBSERVED_AT
            ]
        )
    ),
    ContextGroup(
        description="External environmental atmosphere",
        context=ContextSelection(
            fields=[
                ContextKey.CURRENT_LOCATION,
                ContextKey.OUTSIDE_TEMP_C,
                ContextKey.OBSERVED_AT
            ]
        )
    )
]