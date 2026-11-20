from fractions import Fraction
from typing import Iterable

from issuer.calibration import CalibratedBeat
from issuer.range_codec import RangeEvidence


def trace_range(beats: Iterable[CalibratedBeat], stop_limit: Fraction) -> RangeEvidence:
    """Fold the per-beat changes into exact range evidence.

    After each beat the load as a function of the entry x keeps the closed form
    max(floor, x + shift): shift accumulates the changes and floor accumulates
    max(0, floor + change). A beat stops exactly the entries at or above its
    threshold (the whole domain when its own floor already reaches the limit).
    """
    shift = Fraction(0)
    floor = Fraction(0)
    thresholds = []
    for beat in beats:
        shift += beat.change
        floor = max(Fraction(0), floor + beat.change)
        if floor >= stop_limit:
            threshold = Fraction(0)
        else:
            threshold = max(Fraction(0), stop_limit - shift)
        thresholds.append((beat.beat, threshold))
    return RangeEvidence(tuple(thresholds), shift, floor)
