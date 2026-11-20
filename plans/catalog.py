import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction

from plans.limits import normalize_stop_limit
from plans.segments import SegmentRoster, normalize_label, normalize_segments
from plans.store import load_plan_snapshot, save_plan_snapshot
from plans.units import CalibrationSpec, encode_rational, normalize_calibration


@dataclass(frozen=True)
class PlanRecord:
    plan_id: str
    batch: str
    segments: tuple[SegmentRoster, SegmentRoster]
    calibration: CalibrationSpec
    stop_limit: Fraction


def _make_record(batch, segments, calibration, stop_limit) -> PlanRecord:
    batch = normalize_label(batch, 'batch')
    batch_digest = hashlib.sha256(batch.encode('utf-8')).hexdigest()
    return PlanRecord(
        f'plan-{batch_digest}',
        batch,
        normalize_segments(segments),
        normalize_calibration(calibration),
        normalize_stop_limit(stop_limit),
    )


def encode_plan_record(record: PlanRecord) -> dict:
    return {
        'plan_id': record.plan_id,
        'batch': record.batch,
        'segments': [[roster.name, list(roster.beats)] for roster in record.segments],
        'calibration': [
            encode_rational(record.calibration.multiplier),
            encode_rational(record.calibration.offset),
        ],
        'stop_limit': encode_rational(record.stop_limit),
    }


def decode_plan_record(snapshot: dict) -> PlanRecord:
    if not isinstance(snapshot, dict):
        raise ValueError('plan snapshot must be an object')
    try:
        record = _make_record(
            snapshot['batch'], snapshot['segments'], snapshot['calibration'], snapshot['stop_limit']
        )
    except KeyError as exc:
        raise ValueError('incomplete plan snapshot') from exc
    if snapshot != encode_plan_record(record):
        raise ValueError('noncanonical plan snapshot or wrong plan identity')
    return record


def register_plan(db, batch, segments, calibration, stop_limit) -> str:
    record = _make_record(batch, segments, calibration, stop_limit)
    snapshot = json.dumps(encode_plan_record(record), sort_keys=True, separators=(',', ':'))
    save_plan_snapshot(db, record.plan_id, snapshot)
    return record.plan_id


def read_plan_record(db, plan_id: str) -> PlanRecord:
    record = decode_plan_record(json.loads(load_plan_snapshot(db, plan_id)))
    if record.plan_id != plan_id:
        raise ValueError('stored plan identity mismatch')
    return record
