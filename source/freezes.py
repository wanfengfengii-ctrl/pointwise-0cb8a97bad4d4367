from plans.catalog import read_plan_record
from plans.segments import find_segment_roster
from source.observations import order_complete_observations
from source.revisions import ObservationRevision, decode_observation_revision
from source.store import append_revision_snapshot, load_revision_snapshot


def freeze_observations(db, plan_id, segment, observations, previous_revision_id=None) -> str:
    plan = read_plan_record(db, plan_id)
    roster = find_segment_roster(plan.segments, segment)
    ordered = order_complete_observations(roster, observations)
    if previous_revision_id is not None:
        try:
            parent = read_frozen_revision(db, previous_revision_id)
        except KeyError as exc:
            raise ValueError('unknown amendment parent revision') from exc
        if (parent.plan_id, parent.segment) != (plan.plan_id, roster.name):
            raise ValueError('amendment parent must belong to the same plan segment')
    return append_revision_snapshot(db, plan.plan_id, roster, previous_revision_id, ordered)


def read_frozen_revision(db, revision_id) -> ObservationRevision:
    revision = decode_observation_revision(load_revision_snapshot(db, revision_id))
    if revision.revision_id != revision_id:
        raise ValueError('stored revision identity differs from its lookup key')
    return revision
