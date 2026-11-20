from dataclasses import dataclass
from fractions import Fraction

from plans.units import CalibrationSpec
from source.observations import Observation


@dataclass(frozen=True)
class CalibratedBeat:
    beat: str
    change: Fraction


def calibrate_observations(
    observations: tuple[Observation, ...], calibration: CalibrationSpec
) -> tuple[CalibratedBeat, ...]:
    return tuple(
        CalibratedBeat(row.beat, row.reading * calibration.multiplier + calibration.offset)
        for row in observations
    )
