# TODO
# Decide whether FuelType should remain a shared type or move to context/car.py
# Question: will it be used outside CarContext (e.g. agent contracts?)
from enum import StrEnum


class FuelType(StrEnum):
    PETROL_95 = "petrol_95"
    PETROL_98 = "petrol_98"
    DIESEL    = "diesel"
    LPG       = "lpg"
    ELECTRIC  = "eletric"
