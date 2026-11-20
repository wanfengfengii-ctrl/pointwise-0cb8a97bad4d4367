from dataclasses import dataclass
from fractions import Fraction

from replay.selection import RangeParents


@dataclass(frozen=True)
class RangeVerdict:
    stop_beats: tuple[str, ...]
    exit_range: tuple[Fraction, Fraction, bool, bool] | None


@dataclass(frozen=True)
class _Cap:
    """Upper boundary of an entry set [lower, value] or [lower, value)."""
    value: Fraction
    included: bool


def _min_cap(first: _Cap, second: _Cap) -> _Cap:
    if first.value != second.value:
        return first if first.value < second.value else second
    return _Cap(first.value, first.included and second.included)


def _reaches(lower: Fraction, cap: _Cap) -> bool:
    return lower < cap.value or (lower == cap.value and cap.included)


def _overlaps(lower_a: Fraction, cap_a: _Cap, lower_b: Fraction, cap_b: _Cap) -> bool:
    return _reaches(max(lower_a, lower_b), _min_cap(cap_a, cap_b))


@dataclass(frozen=True)
class _SegmentCurve:
    """Exact segment behaviour: load after beat i is max(floor_i, x + shift_i)."""
    beats: tuple[str, ...]
    thresholds: tuple[Fraction, ...]
    shift: Fraction
    floor: Fraction
    limit: Fraction

    @classmethod
    def from_piece(cls, piece) -> '_SegmentCurve':
        evidence = piece.evidence
        return cls(
            tuple(beat for beat, _ in evidence.thresholds),
            tuple(threshold for _, threshold in evidence.thresholds),
            evidence.exit_shift,
            evidence.exit_floor,
            piece.plan.stop_limit,
        )

    def safe_entry_cap(self) -> Fraction:
        return min([self.limit, *self.thresholds])

    def stop_window(self, index: int) -> tuple[Fraction, Fraction]:
        margin = min([self.limit, *self.thresholds[:index]])
        return self.thresholds[index], margin


def _exit_image(shift: Fraction, floor: Fraction, lower: Fraction, cap: _Cap):
    upper = max(floor, cap.value + shift)
    reachable = cap.included or cap.value + shift <= floor
    return max(floor, lower + shift), upper, reachable


def choose_range_verdict(parents: RangeParents, lo: Fraction, hi: Fraction) -> RangeVerdict:
    front = _SegmentCurve.from_piece(parents.front)
    rear = _SegmentCurve.from_piece(parents.rear)
    query_cap = _Cap(hi, True)

    stops = []
    for index, beat in enumerate(front.beats):
        threshold, margin = front.stop_window(index)
        if _overlaps(threshold, _Cap(margin, False), lo, query_cap):
            stops.append(beat)

    exit_range = None
    front_cap = _min_cap(query_cap, _Cap(front.safe_entry_cap(), False))
    if _reaches(lo, front_cap):
        image_lo, image_hi, image_hi_reached = _exit_image(
            front.shift, front.floor, lo, front_cap
        )
        for index, beat in enumerate(rear.beats):
            threshold, margin = rear.stop_window(index)
            if _overlaps(
                threshold, _Cap(margin, False), image_lo, _Cap(image_hi, image_hi_reached)
            ):
                stops.append(beat)
        rear_safe = rear.safe_entry_cap()
        if front.floor < rear_safe:
            safe_cap = _min_cap(front_cap, _Cap(rear_safe - front.shift, False))
            if _reaches(lo, safe_cap):
                shift = front.shift + rear.shift
                floor = max(rear.floor, front.floor + rear.shift)
                lower = max(floor, lo + shift)
                upper = max(floor, safe_cap.value + shift)
                reachable = safe_cap.included or safe_cap.value + shift <= floor
                exit_range = (lower, upper, True, reachable)
    return RangeVerdict(tuple(stops), exit_range)
