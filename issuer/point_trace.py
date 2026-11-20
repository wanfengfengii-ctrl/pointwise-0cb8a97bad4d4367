from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from issuer.calibration import CalibratedBeat


@dataclass(frozen=True)
class PointTrace:
    stop_beat: str | None
    exit_load: Fraction | None


def trace_point(entry: Fraction, beats: Iterable[CalibratedBeat], stop_limit: Fraction) -> PointTrace:
    load = entry
    for beat in beats:
        load = max(Fraction(0), load + beat.change)
        if load >= stop_limit:
            return PointTrace(beat.beat, None)
    return PointTrace(None, load)
