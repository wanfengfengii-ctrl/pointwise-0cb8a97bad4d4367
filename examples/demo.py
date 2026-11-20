import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.history import read_point_report, read_range_report
from archive.store import initialize_archive_store
from examples.range_fixture import prepare_station
from issuer.pieces import issue_point, issue_range_piece
from issuer.store import initialize_piece_store
from plans.catalog import register_plan
from plans.store import initialize_plan_store
from replay.intake import issue_point_report, issue_range_report
from source.freezes import freeze_observations
from source.observations import Observation
from source.store import initialize_observation_store


def _result(body):
    return {
        'stop_beat': body.stop_beat,
        'exit_load': str(body.exit_load) if body.exit_load is not None else None,
    }


def run_case(order, observations, station_path, center_path):
    with closing(sqlite3.connect(station_path)) as station:
        initialize_plan_store(station)
        initialize_observation_store(station)
        initialize_piece_store(station)
        plan_id = register_plan(
            station, order['batch'], order['segments'], order['calibration'], order['stop_limit']
        )
        front_name, rear_name = (item[0] for item in order['segments'])
        front_id = freeze_observations(
            station, plan_id, front_name, [Observation(*row) for row in observations[front_name]]
        )
        rear_id = freeze_observations(
            station, plan_id, rear_name, [Observation(*row) for row in observations[rear_name]]
        )
        front_piece = issue_point(station, front_id, order['front_entry'])
        rear_entry = front_piece.exit_load
        if rear_entry is None:
            rear_entry = order['rear_entry_if_stopped']
        rear_piece = issue_point(station, rear_id, rear_entry)

    with closing(sqlite3.connect(center_path)) as center:
        initialize_archive_store(center)
        issued = issue_point_report(center, front_piece.encoded, rear_piece.encoded)
    with closing(sqlite3.connect(center_path)) as center:
        initialize_archive_store(center)
        reopened = read_point_report(center, issued.report_id)

    actual = _result(issued.body)
    assert actual == order['expected'], (order['case_id'], actual, order['expected'])
    downstream_expected = {
        'result': order['expected'], 'same_report': True,
        'ordered_parents_retained': True, 'receipt_bound': True,
    }
    downstream_actual = {
        'result': _result(reopened.body),
        'same_report': reopened == issued,
        'ordered_parents_retained': tuple(
            (parent.segment, parent.revision_id, parent.piece_id) for parent in reopened.body.parents
        ) == ((front_name, front_id, front_piece.piece_id), (rear_name, rear_id, rear_piece.piece_id)),
        'receipt_bound': reopened.receipt.report_id == issued.report_id,
    }
    assert downstream_actual == downstream_expected, (order['case_id'], downstream_actual)

    evidence = {
        'case_id': order['case_id'],
        'input': {
            'batch': order['batch'], 'segments': order['segments'], 'stop_limit': order['stop_limit'],
            'calibration': order['calibration'], 'observations': observations,
            'front_entry': order['front_entry'], 'rear_entry': str(rear_piece.entry),
        },
        'expected': order['expected'],
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': [
            'source/freezes.py', 'issuer/pieces.py', 'issuer/point_trace.py', 'replay/intake.py',
            'replay/verdict.py', 'archive/transactions.py', 'archive/history.py',
        ],
        'oracle': order['oracle'],
    }
    print('POINTWISE_SCENARIO ' + json.dumps(evidence, ensure_ascii=False, sort_keys=True))


def _exit_range_text(exit_range):
    if exit_range is None:
        return None
    lower, upper, lower_ok, upper_ok = exit_range
    return f"{'[' if lower_ok else '('}{lower},{upper}{']' if upper_ok else ')'}"


def run_range_cases(scratch):
    station_path = Path(scratch) / 'range-station.sqlite3'
    center_path = Path(scratch) / 'range-center.sqlite3'
    with closing(sqlite3.connect(station_path)) as station:
        revisions = prepare_station(station)
        pieces = {
            key: issue_range_piece(station, revision_id)
            for key, revision_id in revisions.items()
        }
        reissued = issue_range_piece(station, revisions['original'])
        assert (reissued.piece_id, reissued.encoded) == (
            pieces['original'].piece_id, pieces['original'].encoded
        )

    cases = (
        ('R1.window_first_stop', 'original', 'rear', '1', '2', ('p1', 'r1'), '[9/2,5)'),
        ('R2.single_point_front_stop', 'original', 'rear', '2', '2', ('p1',), None),
        ('R3.corrected_amendment', 'corrected', 'rear', '1', '2', ('p1',), None),
        ('R4.floor_single_exit', 'floor_front', 'floor_rear', '1', '2', (), '[4,4]'),
        ('R5.floor_rear_stop', 'floor_front', 'floor_rear', '1', '3', ('r1',), '[4,5)'),
        ('R6.alternate_contrast', 'alternate', 'rear', '2', '2', ('r1',), None),
    )
    signed = {}
    with closing(sqlite3.connect(center_path)) as center:
        initialize_archive_store(center)
        for case_id, front_key, rear_key, lo, hi, stops, exit_text in cases:
            report = issue_range_report(
                center, pieces[front_key].encoded, pieces[rear_key].encoded, lo, hi
            )
            actual = (report.body.stop_beats, _exit_range_text(report.body.exit_range))
            assert actual == (tuple(stops), exit_text), (case_id, actual)
            signed[case_id] = (front_key, rear_key, lo, hi, stops, exit_text, report)

    with closing(sqlite3.connect(center_path)) as center:
        initialize_archive_store(center)
        for case_id, (front_key, rear_key, lo, hi, stops, exit_text, report) in signed.items():
            reopened = read_range_report(center, report.report_id)
            assert reopened == report, case_id
            evidence = {
                'case_id': case_id,
                'entry_window': [lo, hi],
                'expected': {'stop_beats': list(stops), 'exit_range': exit_text},
                'actual': {
                    'stop_beats': list(reopened.body.stop_beats),
                    'exit_range': _exit_range_text(reopened.body.exit_range),
                },
                'parents': [
                    {
                        'piece_id': parent.piece_id,
                        'segment': parent.segment,
                        'revision_id': parent.revision_id,
                    }
                    for parent in reopened.body.parents
                ],
                'report_id': reopened.report_id,
                'receipt_id': reopened.receipt.receipt_id,
                'reopened_same_report': reopened == report,
            }
            print('RANGE_SCENARIO ' + json.dumps(evidence, ensure_ascii=False, sort_keys=True))


def main():
    folder = Path(__file__).resolve().parent
    orders = json.loads((folder / 'runorders.json').read_text(encoding='utf-8'))
    observations = json.loads((folder / 'observations.json').read_text(encoding='utf-8'))
    with TemporaryDirectory(prefix='coating-demo-') as scratch:
        station_path = Path(scratch) / 'station.sqlite3'
        center_path = Path(scratch) / 'center.sqlite3'
        for order in orders:
            run_case(order, observations[order['batch']], station_path, center_path)
        run_range_cases(scratch)


if __name__ == '__main__':
    main()
