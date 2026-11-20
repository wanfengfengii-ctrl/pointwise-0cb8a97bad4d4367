import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction

from issuer.codec import _validate_revision_binding
from plans.catalog import PlanRecord, decode_plan_record, encode_plan_record
from plans.segments import find_segment_roster
from plans.units import encode_rational, normalize_rational


RANGE_PIECE_VERSION = 2


@dataclass(frozen=True)
class RangeEvidence:
    thresholds: tuple[tuple[str, Fraction], ...]
    exit_shift: Fraction
    exit_floor: Fraction


@dataclass(frozen=True)
class RangePiece:
    piece_id: str
    plan: PlanRecord
    segment: str
    revision_id: str
    evidence: RangeEvidence
    encoded: bytes


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')


def _validated_body(plan, segment, revision_id, evidence):
    roster = find_segment_roster(plan.segments, segment)
    _validate_revision_binding(revision_id, plan.plan_id, roster.position)
    if len(evidence.thresholds) != len(roster.beats):
        raise ValueError('range evidence must cover every segment beat')
    thresholds = []
    for beat, entry in zip(roster.beats, evidence.thresholds):
        name, threshold = entry
        if name != beat:
            raise ValueError('range evidence must follow the segment beat order')
        if not isinstance(threshold, Fraction) or threshold < 0:
            raise ValueError('stop threshold requires a nonnegative rational')
        thresholds.append((beat, threshold))
    if not isinstance(evidence.exit_shift, Fraction):
        raise ValueError('exit shift requires an exact rational')
    if not isinstance(evidence.exit_floor, Fraction) or evidence.exit_floor < 0:
        raise ValueError('exit floor requires a nonnegative rational')
    evidence = RangeEvidence(tuple(thresholds), evidence.exit_shift, evidence.exit_floor)
    body = {
        'version': RANGE_PIECE_VERSION,
        'plan': encode_plan_record(plan),
        'segment': roster.name,
        'revision_id': revision_id,
        'evidence': {
            'thresholds': [[beat, encode_rational(threshold)] for beat, threshold in thresholds],
            'exit_shift': encode_rational(evidence.exit_shift),
            'exit_floor': encode_rational(evidence.exit_floor),
        },
    }
    return body, evidence


def _envelope(body: dict) -> tuple[str, bytes]:
    piece_id = 'range-' + hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return piece_id, _canonical_bytes({'piece_id': piece_id, 'body': body})


def encode_range_piece(plan, segment, revision_id, evidence) -> bytes:
    body, _ = _validated_body(plan, segment, revision_id, evidence)
    return _envelope(body)[1]


def _parse_evidence(raw) -> RangeEvidence:
    if not isinstance(raw, dict):
        raise ValueError('range evidence must be an object')
    rows = raw['thresholds']
    if not isinstance(rows, list):
        raise ValueError('range evidence thresholds must be a list')
    thresholds = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2 or not isinstance(row[0], str):
            raise ValueError('each threshold requires a beat name and a rational')
        thresholds.append((row[0], normalize_rational(row[1], 'stop threshold')))
    return RangeEvidence(
        tuple(thresholds),
        normalize_rational(raw['exit_shift'], 'exit shift'),
        normalize_rational(raw['exit_floor'], 'exit floor'),
    )


def decode_range_piece(encoded: bytes) -> RangePiece:
    if not isinstance(encoded, bytes):
        raise ValueError('station piece requires encoded bytes')
    try:
        wire = json.loads(encoded)
        payload = wire['body']
        version = payload['version']
        if type(version) is not int or version != RANGE_PIECE_VERSION:
            raise ValueError('unsupported station piece version')
        plan = decode_plan_record(payload['plan'])
        evidence = _parse_evidence(payload['evidence'])
        body, evidence = _validated_body(
            plan, payload['segment'], payload['revision_id'], evidence
        )
        piece_id, canonical = _envelope(body)
        if encoded != canonical:
            raise ValueError('station piece identity or canonical fields differ')
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f'invalid V2 station piece: {exc}') from exc

    return RangePiece(
        piece_id, plan, body['segment'], body['revision_id'], evidence, encoded
    )
