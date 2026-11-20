from archive.reports import (
    PointReport,
    RangeReport,
    build_point_report_body,
    build_range_report_body,
)
from archive.transactions import commit_point_report, commit_range_report
from issuer.codec import PointPiece, decode_point_piece
from issuer.range_codec import RangePiece, decode_range_piece
from plans.units import normalize_rational
from replay.range_verdict import choose_range_verdict
from replay.selection import select_point_parents, select_range_parents
from replay.verdict import choose_point_verdict


def _decode_input(value: PointPiece | bytes) -> PointPiece:
    if isinstance(value, PointPiece):
        decoded = decode_point_piece(value.encoded)
        if decoded != value:
            raise ValueError('station piece fields differ from its fixed encoding')
        return decoded
    return decode_point_piece(value)


def _decode_range_input(value: RangePiece | bytes) -> RangePiece:
    if isinstance(value, RangePiece):
        decoded = decode_range_piece(value.encoded)
        if decoded != value:
            raise ValueError('station piece fields differ from its fixed encoding')
        return decoded
    return decode_range_piece(value)


def issue_point_report(db, front_piece: PointPiece | bytes, rear_piece: PointPiece | bytes) -> PointReport:
    front = _decode_input(front_piece)
    rear = _decode_input(rear_piece)
    parents = select_point_parents(front, rear)
    verdict = choose_point_verdict(parents)
    return commit_point_report(db, build_point_report_body(parents, verdict))


def issue_range_report(
    db, front_piece: RangePiece | bytes, rear_piece: RangePiece | bytes, lo, hi
) -> RangeReport:
    front = _decode_range_input(front_piece)
    rear = _decode_range_input(rear_piece)
    parents = select_range_parents(front, rear)
    lo = normalize_rational(lo, 'entry window lower bound')
    hi = normalize_rational(hi, 'entry window upper bound')
    if not 0 <= lo <= hi < parents.front.plan.stop_limit:
        raise ValueError('entry window must satisfy 0 <= lo <= hi < stop limit')
    verdict = choose_range_verdict(parents, lo, hi)
    return commit_range_report(db, build_range_report_body(parents, lo, hi, verdict))
