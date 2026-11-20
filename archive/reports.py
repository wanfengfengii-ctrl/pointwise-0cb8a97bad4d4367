import json
from dataclasses import dataclass
from fractions import Fraction

from archive.receipts import PointReceipt, RangeReceipt
from plans.units import encode_rational, normalize_rational
from replay.range_verdict import RangeVerdict
from replay.selection import PointParents, RangeParents
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


@dataclass(frozen=True)
class RangeParentRef:
    piece_id: str
    segment: str
    revision_id: str


@dataclass(frozen=True)
class RangeReportBody:
    plan_id: str
    parents: tuple[RangeParentRef, RangeParentRef]
    entry_window: tuple[Fraction, Fraction]
    stop_beats: tuple[str, ...]
    exit_range: tuple[Fraction, Fraction, bool, bool] | None


@dataclass(frozen=True)
class RangeReport:
    report_id: int
    body: RangeReportBody
    receipt: RangeReceipt


def build_range_report_body(
    parents: RangeParents, lo: Fraction, hi: Fraction, verdict: RangeVerdict
) -> RangeReportBody:
    refs = (
        RangeParentRef(parents.front.piece_id, parents.front.segment, parents.front.revision_id),
        RangeParentRef(parents.rear.piece_id, parents.rear.segment, parents.rear.revision_id),
    )
    return RangeReportBody(
        parents.front.plan.plan_id, refs, (lo, hi), tuple(verdict.stop_beats), verdict.exit_range
    )


def encode_range_report_body(body: RangeReportBody) -> str:
    payload = {
        'plan_id': body.plan_id,
        'parents': [
            {
                'piece_id': parent.piece_id,
                'segment': parent.segment,
                'revision_id': parent.revision_id,
            }
            for parent in body.parents
        ],
        'entry_window': [
            encode_rational(body.entry_window[0]), encode_rational(body.entry_window[1])
        ],
        'stop_beats': list(body.stop_beats),
        'exit_range': (
            [
                encode_rational(body.exit_range[0]),
                encode_rational(body.exit_range[1]),
                body.exit_range[2],
                body.exit_range[3],
            ]
            if body.exit_range is not None
            else None
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


def decode_range_report_body(encoded: str) -> RangeReportBody:
    try:
        payload = json.loads(encoded)
        if not isinstance(payload, dict) or not isinstance(payload['plan_id'], str):
            raise ValueError('range report body must be an object with a plan identity')
        parents = payload['parents']
        if not isinstance(parents, list) or len(parents) != 2:
            raise ValueError('range report requires two ordered parents')
        refs = tuple(
            RangeParentRef(entry['piece_id'], entry['segment'], entry['revision_id'])
            for entry in parents
        )
        window = payload['entry_window']
        if not isinstance(window, list) or len(window) != 2:
            raise ValueError('range report requires a two point entry window')
        lo = normalize_rational(window[0], 'archived window')
        hi = normalize_rational(window[1], 'archived window')
        if lo > hi:
            raise ValueError('archived entry window is inverted')
        beats = payload['stop_beats']
        if not isinstance(beats, list) or not all(type(beat) is str for beat in beats):
            raise ValueError('archived stop beats must be beat names')
        raw_exit = payload['exit_range']
        if raw_exit is None:
            exit_range = None
        else:
            if not isinstance(raw_exit, list) or len(raw_exit) != 4:
                raise ValueError('archived exit range requires bounds and reachability')
            lower = normalize_rational(raw_exit[0], 'archived exit')
            upper = normalize_rational(raw_exit[1], 'archived exit')
            if type(raw_exit[2]) is not bool or type(raw_exit[3]) is not bool:
                raise ValueError('archived exit reachability must be boolean')
            exit_range = (lower, upper, raw_exit[2], raw_exit[3])
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise ValueError(f'invalid stored range report body: {exc}') from exc
    return RangeReportBody(payload['plan_id'], refs, (lo, hi), tuple(beats), exit_range)
