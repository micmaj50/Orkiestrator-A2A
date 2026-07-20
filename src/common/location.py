from enum import StrEnum

from pydantic import Field

from .model_config import ConfiguredBaseModel

class Coordinates(ConfiguredBaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


# class Address(ConfiguredBaseModel):
