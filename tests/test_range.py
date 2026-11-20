import hashlib
import json
import sqlite3
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

from archive.history import read_point_report, read_range_report
from examples.range_fixture import prepare_station
from issuer.codec import decode_point_piece
from issuer.pieces import issue_point, issue_range_piece
from issuer.range_codec import decode_range_piece
from plans.catalog import read_plan_record
from replay.intake import issue_point_report, issue_range_report
from tests.support import LedgerCase


def _repack_range(encoded, **fields):
    wire = json.loads(encoded)
    wire['body'].update(fields)
    payload = json.dumps(wire['body'], sort_keys=True, separators=(',', ':')).encode('ascii')
    wire['piece_id'] = 'range-' + hashlib.sha256(payload).hexdigest()
    return json.dumps(wire, sort_keys=True, separators=(',', ':')).encode('ascii')


class RangeCase(LedgerCase):
    def setUp(self):
        super().setUp()
        self.revisions = prepare_station(self.station)
        self.pieces = {
            key: issue_range_piece(self.station, revision_id)
            for key, revision_id in self.revisions.items()
        }

    def range_counts(self):
        return self.center.execute(
            'SELECT (SELECT COUNT(*) FROM range_reports), '
            '(SELECT COUNT(*) FROM range_report_receipts)'
        ).fetchone()

    def range_piece_count(self):
        return self.station.execute('SELECT COUNT(*) FROM range_pieces').fetchone()[0]

    def sign(self, front_key, rear_key, lo, hi):
        return issue_range_report(
            self.center, self.pieces[front_key], self.pieces[rear_key], lo, hi
        )


class RangePieceTests(RangeCase):
    def test_public_fields(self):
        piece = self.pieces['original']
        self.assertEqual(piece.segment, 'front')
        self.assertEqual(piece.revision_id, self.revisions['original'])
        self.assertIsInstance(piece.encoded, bytes)
        self.assertEqual(piece.plan, read_plan_record(self.station, piece.plan.plan_id))
        self.assertEqual(decode_range_piece(piece.encoded), piece)

    def test_reissue_same_revision(self):
        again = issue_range_piece(self.station, self.revisions['original'])
        self.assertEqual(again, self.pieces['original'])
        self.assertEqual(
            (again.piece_id, again.encoded),
            (self.pieces['original'].piece_id, self.pieces['original'].encoded),
        )
        self.assertEqual(self.range_piece_count(), 6)

    def test_reissue_after_reopen(self):
        self.station.close()
        self.open_station()
        again = issue_range_piece(self.station, self.revisions['floor_front'])
        self.assertEqual(again, self.pieces['floor_front'])
        self.assertEqual(self.range_piece_count(), 6)

    def test_unknown_revision(self):
        with self.assertRaises(KeyError):
            issue_range_piece(self.station, 'unknown-revision')
        self.assertEqual(self.range_piece_count(), 6)

    def test_decode_after_station_close(self):
        encoded = self.pieces['original'].encoded
        self.station.close()
        piece = decode_range_piece(encoded)
        self.assertEqual(piece.piece_id, self.pieces['original'].piece_id)
        self.assertEqual(piece.plan.stop_limit, 5)

    def test_bad_envelopes(self):
        piece = self.pieces['original']
        rear_revision = self.revisions['rear']
        for bad in (
            _repack_range(piece.encoded, version=1),
            _repack_range(piece.encoded, version=True),
            _repack_range(piece.encoded, version='2'),
            piece.encoded[:-3],
            b'not json',
            _repack_range(piece.encoded, revision_id=rear_revision),
            _repack_range(piece.encoded, segment='rear'),
            _repack_range(
                piece.encoded,
                evidence={'thresholds': [['p1', '2'], ['p2', '3']],
                          'exit_shift': '2', 'exit_floor': '-1'},
            ),
            _repack_range(
                piece.encoded,
                evidence={'thresholds': [['p2', '3'], ['p1', '2']],
                          'exit_shift': '2', 'exit_floor': '2'},
            ),
            _repack_range(
                piece.encoded,
                evidence={'thresholds': [['p1', '-1'], ['p2', '3']],
                          'exit_shift': '2', 'exit_floor': '2'},
            ),
            piece.encoded.replace(b'"exit_shift":"2"', b'"exit_shift":"2.0"'),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    decode_range_piece(bad)

    def test_version_isolation(self):
        point = issue_point(self.station, self.revisions['original'], 1)
        with self.assertRaises(ValueError):
            decode_range_piece(point.encoded)
        with self.assertRaises(ValueError):
            decode_point_piece(self.pieces['original'].encoded)


class RangeReportTests(RangeCase):
    def test_sample_table(self):
        self.station.close()
        cases = (
            ('original', 'rear', 1, 2, ('p1', 'r1'), (Fraction(9, 2), Fraction(5), True, False)),
            ('original', 'rear', 2, 2, ('p1',), None),
            ('corrected', 'rear', 1, 2, ('p1',), None),
            ('floor_front', 'floor_rear', 1, 2, (), (Fraction(4), Fraction(4), True, True)),
            ('floor_front', 'floor_rear', 1, 3, ('r1',), (Fraction(4), Fraction(5), True, False)),
            ('alternate', 'rear', 2, 2, ('r1',), None),
        )
        for front_key, rear_key, lo, hi, stops, exit_range in cases:
            with self.subTest(front=front_key, rear=rear_key, lo=lo, hi=hi):
                report = self.sign(front_key, rear_key, lo, hi)
                body = report.body
                self.assertEqual(body.stop_beats, stops)
                self.assertEqual(body.exit_range, exit_range)
                self.assertEqual(body.entry_window, (Fraction(lo), Fraction(hi)))
                self.assertEqual(body.plan_id, self.pieces[front_key].plan.plan_id)
                self.assertEqual(
                    tuple(parent.segment for parent in body.parents), ('front', 'rear')
                )
                self.assertEqual(
                    tuple(parent.revision_id for parent in body.parents),
                    (self.revisions[front_key], self.revisions[rear_key]),
                )
                self.assertEqual(
                    tuple(parent.piece_id for parent in body.parents),
                    (self.pieces[front_key].piece_id, self.pieces[rear_key].piece_id),
                )
                self.assertEqual(report.receipt.report_id, report.report_id)
                self.assertEqual(
                    report.receipt.receipt_id, f'range-receipt-{report.report_id}'
                )
                self.assertEqual(read_range_report(self.center, report.report_id), report)
        self.assertEqual(self.range_counts(), (6, 6))

    def test_safe_window_and_boundary(self):
        self.station.close()
        safe = self.sign('original', 'rear', 0, 1)
        self.assertEqual(safe.body.stop_beats, ())
        self.assertEqual(
            safe.body.exit_range, (Fraction(7, 2), Fraction(9, 2), True, True)
        )
        edge = self.sign('original', 'rear', Fraction(3, 2), Fraction(3, 2))
        self.assertEqual(edge.body.stop_beats, ('r1',))
        self.assertIsNone(edge.body.exit_range)
        self.assertEqual(self.range_counts(), (2, 2))

    def test_window_validation(self):
        self.station.close()
        for lo, hi in (
            (-1, 2), (2, 1), (1, 5), (0, 5), (5, 5), (1, '5.0'), ('1/0', 2),
            (True, 2), (1, False), (1.5, 2), (2, 2.0), (None, 2), (2, None),
            (Decimal('NaN'), 2), (Decimal('Infinity'), 2), ('', 2), ('x', 2),
        ):
            with self.subTest(lo=lo, hi=hi):
                with self.assertRaises(ValueError):
                    self.sign('original', 'rear', lo, hi)
        self.assertEqual(self.range_counts(), (0, 0))

    def test_window_input_forms(self):
        self.station.close()
        report = self.sign('floor_front', 'floor_rear', '1.5', Decimal('2.0'))
        self.assertEqual(report.body.entry_window, (Fraction(3, 2), Fraction(2)))
        single = self.sign('floor_front', 'floor_rear', 0, 0)
        self.assertEqual(single.body.exit_range, (Fraction(4), Fraction(4), True, True))
        self.assertEqual(self.range_counts(), (2, 2))

    def test_selection_mismatch(self):
        self.station.close()
        front = self.pieces['original']
        rear = self.pieces['rear']
        floor_front = self.pieces['floor_front']
        floor_rear = self.pieces['floor_rear']
        corrected = self.pieces['corrected']
        for first, second in (
            (front, floor_rear),
            (floor_front, rear),
            (corrected, floor_rear),
            (rear, front),
            (front, front),
            (rear, rear),
        ):
            with self.subTest(first=first.segment, second=second.segment):
                with self.assertRaises(ValueError):
                    issue_range_report(self.center, first, second, 1, 2)
        self.assertEqual(self.range_counts(), (0, 0))

    def test_mixed_versions(self):
        point_front = issue_point(self.station, self.revisions['original'], 1)
        point_rear = issue_point(self.station, self.revisions['rear'], 4)
        self.station.close()
        range_front = self.pieces['original']
        range_rear = self.pieces['rear']
        for first, second in (
            (point_front.encoded, range_rear.encoded),
            (range_front.encoded, point_rear.encoded),
            (point_front.encoded, point_rear.encoded),
            (point_front, range_rear),
            (range_front, point_rear),
        ):
            with self.subTest(first=type(first), second=type(second)):
                with self.assertRaises(ValueError):
                    issue_range_report(self.center, first, second, 1, 2)
        with self.assertRaises(ValueError):
            issue_point_report(self.center, range_front.encoded, range_rear.encoded)
        with self.assertRaises(ValueError):
            issue_point_report(self.center, range_front, range_rear)
        self.assertEqual(self.range_counts(), (0, 0))
        self.assertEqual(self.archive_counts(), (0, 0))

    def test_object_field_mismatch(self):
        forged = replace(self.pieces['original'], segment='rear')
        self.station.close()
        with self.assertRaises(ValueError):
            issue_range_report(self.center, forged, self.pieces['rear'], 1, 2)
        self.assertEqual(self.range_counts(), (0, 0))

    def test_bytes_and_object_inputs(self):
        self.station.close()
        by_object = self.sign('original', 'rear', 1, 2)
        by_bytes = issue_range_report(
            self.center,
            self.pieces['original'].encoded,
            self.pieces['rear'].encoded,
            1,
            2,
        )
        self.assertNotEqual(by_object.report_id, by_bytes.report_id)
        self.assertEqual(by_object.body, by_bytes.body)
        self.assertEqual(self.range_counts(), (2, 2))

    def test_commit_rollback_and_retry(self):
        self.station.close()
        self.center.execute('''
            CREATE TEMP TRIGGER reject_range_receipt
            BEFORE INSERT ON range_report_receipts
            WHEN EXISTS (SELECT 1 FROM range_reports WHERE report_id = NEW.report_id)
            BEGIN
                SELECT RAISE(ABORT, 'range receipt rejected after report write');
            END
        ''')
        with self.assertRaises(sqlite3.IntegrityError) as raised:
            self.sign('original', 'rear', 1, 2)
        self.assertEqual(raised.exception.args, ('range receipt rejected after report write',))
        self.assertFalse(self.center.in_transaction)
        self.assertEqual(self.range_counts(), (0, 0))
        self.center.execute('DROP TRIGGER reject_range_receipt')
        report = self.sign('original', 'rear', 1, 2)
        self.assertEqual(self.range_counts(), (1, 1))
        self.assertEqual(read_range_report(self.center, report.report_id), report)

    def test_reopen_and_amendment(self):
        original_report = self.sign('original', 'rear', 1, 2)
        corrected_report = self.sign('corrected', 'rear', 1, 2)
        self.assertNotEqual(original_report.report_id, corrected_report.report_id)
        self.station.close()
        self.center.close()
        self.open_center()
        stored_original = read_range_report(self.center, original_report.report_id)
        stored_corrected = read_range_report(self.center, corrected_report.report_id)
        self.assertEqual(stored_original, original_report)
        self.assertEqual(stored_corrected, corrected_report)
        self.assertEqual(stored_original.body.stop_beats, ('p1', 'r1'))
        self.assertEqual(
            stored_original.body.exit_range, (Fraction(9, 2), Fraction(5), True, False)
        )
        self.assertEqual(stored_corrected.body.stop_beats, ('p1',))
        self.assertIsNone(stored_corrected.body.exit_range)
        self.assertEqual(
            stored_original.body.parents[0].revision_id, self.revisions['original']
        )
        self.assertEqual(
            stored_corrected.body.parents[0].revision_id, self.revisions['corrected']
        )
        self.assertEqual(self.range_counts(), (2, 2))

    def test_unknown_report(self):
        point_front = issue_point(self.station, self.revisions['original'], 1)
        point_rear = issue_point(self.station, self.revisions['rear'], 3)
        self.station.close()
        report = self.sign('original', 'rear', 1, 2)
        with self.assertRaises(KeyError):
            read_range_report(self.center, report.report_id + 1)
        with self.assertRaises(KeyError):
            read_range_report(self.center, '1')
        with self.assertRaises(KeyError):
            read_point_report(self.center, report.report_id)
        point = issue_point_report(self.center, point_front, point_rear)
        self.assertEqual(point.report_id, report.report_id)
        self.assertEqual(read_range_report(self.center, point.report_id), report)
        self.assertEqual(read_point_report(self.center, point.report_id), point)
        self.assertEqual(self.range_counts(), (1, 1))

    def test_stop_beats_plan_order(self):
        plan_id = self.make_plan(front=('p1', 'p2'), rear=('r1',))
        front_id = self.freeze(plan_id, 'front', [('p1', 1, 'ok'), ('p2', 3, 'ok')])
        rear_id = self.freeze(plan_id, 'rear', [('r1', 0, 'ok')])
        front = issue_range_piece(self.station, front_id)
        rear = issue_range_piece(self.station, rear_id)
        self.station.close()
        report = issue_range_report(self.center, front, rear, 0, 4)
        self.assertEqual(report.body.stop_beats, ('p1', 'p2'))
        self.assertEqual(
            report.body.exit_range, (Fraction(4), Fraction(5), True, False)
        )

    def test_flat_tail_exit_single_point(self):
        plan_id = self.make_plan(front=('p1',), rear=('r1', 'r2', 'r3'))
        front_id = self.freeze(plan_id, 'front', [('p1', 0, 'ok')])
        rear_id = self.freeze(
            plan_id, 'rear', [('r1', 4, 'ok'), ('r2', -10, 'ok'), ('r3', 1, 'ok')]
        )
        front = issue_range_piece(self.station, front_id)
        rear = issue_range_piece(self.station, rear_id)
        self.station.close()
        report = issue_range_report(self.center, front, rear, 0, 4)
        self.assertEqual(report.body.stop_beats, ('r1',))
        self.assertEqual(report.body.exit_range, (Fraction(1), Fraction(1), True, True))

    def test_v1_flow_unaffected(self):
        front = issue_point(self.station, self.revisions['original'], 1)
        rear = issue_point(self.station, self.revisions['rear'], front.exit_load)
        self.station.close()
        report = issue_point_report(self.center, front, rear)
        self.assertEqual((report.body.stop_beat, report.body.exit_load), (None, Fraction(9, 2)))
        self.assertEqual(read_point_report(self.center, report.report_id), report)
        self.assertEqual(self.range_counts(), (0, 0))
