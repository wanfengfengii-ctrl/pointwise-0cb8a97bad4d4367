from dataclasses import dataclass

from issuer.codec import PointPiece
from issuer.range_codec import RangePiece


@dataclass(frozen=True)
class PointParents:
    front: PointPiece
    rear: PointPiece


def select_point_parents(front: PointPiece, rear: PointPiece) -> PointParents:
    if front.plan != rear.plan:
        raise ValueError('station pieces must belong to the same fixed plan')
    expected = tuple(roster.name for roster in front.plan.segments)
    if (front.segment, rear.segment) != expected:
        raise ValueError('station pieces must follow the two plan segments in order')
    return PointParents(front, rear)


@dataclass(frozen=True)
class RangeParents:
    front: RangePiece
    rear: RangePiece


def select_range_parents(front: RangePiece, rear: RangePiece) -> RangeParents:
    if front.plan != rear.plan:
        raise ValueError('station pieces must belong to the same fixed plan')
    expected = tuple(roster.name for roster in front.plan.segments)
    if (front.segment, rear.segment) != expected:
        raise ValueError('station pieces must follow the two plan segments in order')
    return RangeParents(front, rear)
