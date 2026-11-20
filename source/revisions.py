import hashlib
import json
from dataclasses import dataclass

from plans.units import encode_rational, normalize_rational
from source.observations import Observation


@dataclass(frozen=True)
class ObservationRevision:
    revision_id: str
    plan_id: str
    segment: str
    position: int
    sequence: int
    previous_revision_id: str | None
    observations: tuple[Observation, ...]


def _canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _snapshot(plan_id, segment, position, sequence, previous_revision_id, observations) -> dict:
    return {
        'plan_id': plan_id,
        'segment': segment,
        'position': position,
        'sequence': sequence,
        'previous_revision_id': previous_revision_id,
        'observations': [
            [row.beat, encode_rational(row.reading), row.quality] for row in observations
        ],
    }


def build_observation_revision(
    plan_id: str,
    segment: str,
    position: int,
    sequence: int,
    previous_revision_id: str | None,
    observations: tuple[Observation, ...],
) -> ObservationRevision:
    snapshot = _snapshot(plan_id, segment, position, sequence, previous_revision_id, observations)
    digest = hashlib.sha256(_canonical_json(snapshot).encode('ascii')).hexdigest()
    return ObservationRevision(
        f'{plan_id}/{position}/{digest}',
        plan_id,
        segment,
        position,
        sequence,
        previous_revision_id,
        observations,
    )


def encode_observation_revision(revision: ObservationRevision) -> str:
    snapshot = _snapshot(
        revision.plan_id,
        revision.segment,
        revision.position,
        revision.sequence,
        revision.previous_revision_id,
        revision.observations,
    )
    snapshot['revision_id'] = revision.revision_id
    return _canonical_json(snapshot)


def decode_observation_revision(encoded: str) -> ObservationRevision:
    snapshot = json.loads(encoded)
    observations = tuple(
        Observation(beat, normalize_rational(reading, 'stored reading'), quality)
        for beat, reading, quality in snapshot['observations']
    )
    revision = build_observation_revision(
        snapshot['plan_id'],
        snapshot['segment'],
        snapshot['position'],
        snapshot['sequence'],
        snapshot['previous_revision_id'],
        observations,
    )
    if encode_observation_revision(revision) != encoded:
        raise ValueError('stored observation revision identity mismatch')
    return revision
