import sqlite3
from contextlib import closing
from fractions import Fraction

from archive.history import read_point_report
from archive.store import initialize_archive_store
from issuer.pieces import issue_point
from issuer.store import initialize_piece_store
from plans.catalog import register_plan
from plans.store import initialize_plan_store
from replay.intake import issue_point_report
from source.freezes import freeze_observations
from source.observations import Observation
from source.store import initialize_observation_store


def prepare_station(station):
    initialize_plan_store(station)
    initialize_observation_store(station)
    initialize_piece_store(station)
    segments = (("front", ("p1", "p2")), ("rear", ("r1",)))
    incident = register_plan(station, "LQ-RANGE-01", segments, (1, 0), 5)
    plateau = register_plan(station, "LQ-RANGE-02", segments, (1, 0), 5)

    def freeze(plan, segment, rows, previous=None):
        observations = [Observation(beat, reading, "ok") for beat, reading in rows]
        return freeze_observations(station, plan, segment, observations, previous)

    original = freeze(incident, "front", (("p1", 3), ("p2", -1)))
    return {
        "original": original,
        "alternate": freeze(incident, "front", (("p1", 1), ("p2", 1))),
        "corrected": freeze(incident, "front", (("p1", 4), ("p2", -1)), original),
        "rear": freeze(incident, "rear", (("r1", "3/2"),)),
        "floor_front": freeze(plateau, "front", (("p1", -2), ("p2", 1))),
        "floor_rear": freeze(plateau, "rear", (("r1", 3),)),
    }


def main():
    # These are individual V1 readings, not a range evaluator.
    cases = (
        ("original", "rear", "1", (None, 3), (None, Fraction(9, 2))),
        ("alternate", "rear", "1", (None, 3), (None, Fraction(9, 2))),
        ("original", "rear", "3/2", (None, Fraction(7, 2)), ("r1", None)),
        ("original", "rear", "2", ("p1", None), ("p1", None)),
        ("alternate", "rear", "2", (None, 4), ("r1", None)),
        ("corrected", "rear", "1", ("p1", None), ("p1", None)),
        ("floor_front", "floor_rear", "1", (None, 1), (None, 4)),
        ("floor_front", "floor_rear", "2", (None, 1), (None, 4)),
        ("floor_front", "floor_rear", "3", (None, 2), ("r1", None)),
    )
    samples = []
    with closing(sqlite3.connect(":memory:")) as station:
        revisions = prepare_station(station)
        for front_key, rear_key, entry, expected_front, expected_report in cases:
            front = issue_point(station, revisions[front_key], entry)
            assert (front.stop_beat, front.exit_load) == expected_front, (front_key, entry)
            rear_entry = front.exit_load if front.exit_load is not None else 0
            rear = issue_point(station, revisions[rear_key], rear_entry)
            samples.append((front_key, entry, front.encoded, rear.encoded, expected_report))

    with closing(sqlite3.connect(":memory:")) as center:
        initialize_archive_store(center)
        for front_key, entry, front, rear, expected in samples:
            report = issue_point_report(center, front, rear)
            assert (report.body.stop_beat, report.body.exit_load) == expected, (front_key, entry)
            assert read_point_report(center, report.report_id) == report
            print(f"{front_key} entry={entry} stop={report.body.stop_beat} exit={report.body.exit_load}")


if __name__ == "__main__":
    main()
