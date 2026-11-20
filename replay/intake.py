from archive.reports import PointReport, build_point_report_body
from archive.transactions import commit_point_report
from issuer.codec import PointPiece, decode_point_piece
from replay.selection import select_point_parents
from replay.verdict import choose_point_verdict


def _decode_input(value: PointPiece | bytes) -> PointPiece:
    if isinstance(value, PointPiece):
        decoded = decode_point_piece(value.encoded)
        if decoded != value:
            raise ValueError('station piece fields differ from its fixed encoding')
        return decoded
    return decode_point_piece(value)


def issue_point_report(db, front_piece: PointPiece | bytes, rear_piece: PointPiece | bytes) -> PointReport:
    front = _decode_input(front_piece)
    rear = _decode_input(rear_piece)
    parents = select_point_parents(front, rear)
    verdict = choose_point_verdict(parents)
    return commit_point_report(db, build_point_report_body(parents, verdict))
