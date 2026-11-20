import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction

from plans.catalog import PlanRecord, decode_plan_record, encode_plan_record
from plans.limits import validate_safe_load
from plans.segments import find_segment_roster
from plans.units import encode_rational


POINT_PIECE_VERSION = 1


@dataclass(frozen=True)
class PointPiece:
    piece_id: str
    plan: PlanRecord
    segment: str
    revision_id: str
    entry: Fraction
    stop_beat: str | None
    exit_load: Fraction | None
    encoded: bytes


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')


def _validate_revision_binding(revision_id: str, plan_id: str, position: int) -> None:
    prefix = f'{plan_id}/{position}/'
    if not isinstance(revision_id, str) or not revision_id.startswith(prefix):
        raise ValueError('revision identity is outside the piece plan segment')
    digest = revision_id[len(prefix):]
    if len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest):
        raise ValueError('malformed revision identity')


def _validated_body(plan, segment, revision_id, entry, stop_beat, exit_load):
    roster = find_segment_roster(plan.segments, segment)
    _validate_revision_binding(revision_id, plan.plan_id, roster.position)
    entry = validate_safe_load(entry, plan.stop_limit)
    if stop_beat is None:
        exit_load = validate_safe_load(exit_load, plan.stop_limit, 'safe exit')
    elif stop_beat not in roster.beats or exit_load is not None:
        raise ValueError('invalid stop beat or competing safe exit')
    body = {
        'version': POINT_PIECE_VERSION,
        'plan': encode_plan_record(plan),
        'segment': roster.name,
        'revision_id': revision_id,
        'entry': encode_rational(entry),
        'stop_beat': stop_beat,
        'exit_load': encode_rational(exit_load) if exit_load is not None else None,
    }
    return body, entry, exit_load


def _envelope(body: dict) -> tuple[str, bytes]:
    piece_id = 'point-' + hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return piece_id, _canonical_bytes({'piece_id': piece_id, 'body': body})


def encode_point_piece(plan, segment, revision_id, entry, stop_beat, exit_load) -> bytes:
    body, _, _ = _validated_body(plan, segment, revision_id, entry, stop_beat, exit_load)
    return _envelope(body)[1]


def decode_point_piece(encoded: bytes) -> PointPiece:
    if not isinstance(encoded, bytes):
        raise ValueError('station piece requires encoded bytes')
    try:
        wire = json.loads(encoded)
        payload = wire['body']
        version = payload['version']
        if type(version) is not int or version != POINT_PIECE_VERSION:
            raise ValueError('unsupported station piece version')
        plan = decode_plan_record(payload['plan'])
        body, entry, exit_load = _validated_body(
            plan, payload['segment'], payload['revision_id'], payload['entry'],
            payload['stop_beat'], payload['exit_load'],
        )
        piece_id, canonical = _envelope(body)
        if encoded != canonical:
            raise ValueError('station piece identity or canonical fields differ')
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f'invalid V1 station piece: {exc}') from exc

    return PointPiece(
        piece_id, plan, body['segment'], body['revision_id'], entry,
        body['stop_beat'], exit_load, encoded,
    )
