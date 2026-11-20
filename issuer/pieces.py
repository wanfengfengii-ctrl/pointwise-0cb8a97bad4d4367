from issuer.calibration import calibrate_observations
from issuer.codec import PointPiece, decode_point_piece, encode_point_piece
from issuer.point_trace import trace_point
from issuer.range_codec import RangePiece, decode_range_piece, encode_range_piece
from issuer.range_trace import trace_range
from issuer.store import (
    find_issued_piece,
    find_issued_range_piece,
    save_or_get_issued_piece,
    save_or_get_issued_range_piece,
)
from plans.catalog import read_plan_record
from plans.limits import validate_safe_load
from plans.units import encode_rational
from source.freezes import read_frozen_revision


def issue_point(db, revision_id, entry) -> PointPiece:
    revision = read_frozen_revision(db, revision_id)
    plan = read_plan_record(db, revision.plan_id)
    entry = validate_safe_load(entry, plan.stop_limit)
    entry_key = encode_rational(entry)
    stored = find_issued_piece(db, revision.revision_id, entry_key)
    if stored is not None:
        return decode_point_piece(stored)

    beats = calibrate_observations(revision.observations, plan.calibration)
    trace = trace_point(entry, beats, plan.stop_limit)
    encoded = encode_point_piece(
        plan, revision.segment, revision.revision_id, entry, trace.stop_beat, trace.exit_load
    )
    candidate = decode_point_piece(encoded)
    fixed = save_or_get_issued_piece(
        db, revision.revision_id, entry_key, candidate.piece_id, encoded
    )
    return candidate if fixed == encoded else decode_point_piece(fixed)


def issue_range_piece(db, revision_id) -> RangePiece:
    revision = read_frozen_revision(db, revision_id)
    stored = find_issued_range_piece(db, revision.revision_id)
    if stored is not None:
        return decode_range_piece(stored)

    plan = read_plan_record(db, revision.plan_id)
    beats = calibrate_observations(revision.observations, plan.calibration)
    evidence = trace_range(beats, plan.stop_limit)
    encoded = encode_range_piece(plan, revision.segment, revision.revision_id, evidence)
    candidate = decode_range_piece(encoded)
    fixed = save_or_get_issued_range_piece(
        db, revision.revision_id, candidate.piece_id, encoded
    )
    return candidate if fixed == encoded else decode_range_piece(fixed)
