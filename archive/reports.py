import json
from dataclasses import dataclass
from fractions import Fraction

from archive.receipts import PointReceipt
from plans.units import encode_rational, normalize_rational
from replay.selection import PointParents
from replay.verdict import PointVerdict


@dataclass(frozen=True)
class ParentPieceRef:
    piece_id: str
    segment: str
    revision_id: str
    entry: Fraction


@dataclass(frozen=True)
class PointReportBody:
    plan_id: str
    parents: tuple[ParentPieceRef, ParentPieceRef]
    stop_beat: str | None
    exit_load: Fraction | None


@dataclass(frozen=True)
class PointReport:
    report_id: int
    body: PointReportBody
    receipt: PointReceipt


def _parent_ref(piece) -> ParentPieceRef:
    return ParentPieceRef(piece.piece_id, piece.segment, piece.revision_id, piece.entry)


def build_point_report_body(parents: PointParents, verdict: PointVerdict) -> PointReportBody:
    return PointReportBody(
        parents.front.plan.plan_id,
        (_parent_ref(parents.front), _parent_ref(parents.rear)),
        verdict.stop_beat,
        verdict.exit_load,
    )


def encode_report_body(body: PointReportBody) -> str:
    payload = {
        'plan_id': body.plan_id,
        'parents': [
            {
                'piece_id': parent.piece_id,
                'segment': parent.segment,
                'revision_id': parent.revision_id,
                'entry': encode_rational(parent.entry),
            }
            for parent in body.parents
        ],
        'stop_beat': body.stop_beat,
        'exit_load': encode_rational(body.exit_load) if body.exit_load is not None else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


def decode_report_body(encoded: str) -> PointReportBody:
    payload = json.loads(encoded)
    front, rear = (
        ParentPieceRef(
            entry['piece_id'], entry['segment'], entry['revision_id'],
            normalize_rational(entry['entry'], 'archived entry'),
        )
        for entry in payload['parents']
    )
    exit_load = payload['exit_load']
    return PointReportBody(
        payload['plan_id'], (front, rear), payload['stop_beat'],
        normalize_rational(exit_load, 'archived exit') if exit_load is not None else None,
    )
