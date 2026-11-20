from dataclasses import dataclass
from fractions import Fraction

from replay.handoff import require_point_handoff
from replay.selection import PointParents


@dataclass(frozen=True)
class PointVerdict:
    stop_beat: str | None
    exit_load: Fraction | None


def choose_point_verdict(parents: PointParents) -> PointVerdict:
    if parents.front.stop_beat is not None:
        return PointVerdict(parents.front.stop_beat, None)
    require_point_handoff(parents)
    return PointVerdict(parents.rear.stop_beat, parents.rear.exit_load)
