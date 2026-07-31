from pydantic import Field
from typing import Literal

from .model_config import ConfiguredBaseModel

class TirePressure(ConfiguredBaseModel):
    """Individual tire pressures, typically measured in bar or psi."""
    front_left: float | None = Field(default=None, ge=0)
    front_right: float | None = Field(default=None, ge=0)
    rear_left: float | None = Field(default=None, ge=0)
    rear_right: float | None = Field(default=None, ge=0)
    unit: Literal["bar", "psi"] = "bar"