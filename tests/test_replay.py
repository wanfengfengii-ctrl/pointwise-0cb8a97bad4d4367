import hashlib
import json
from dataclasses import replace

from archive.history import read_point_report
from issuer.pieces import issue_point
from replay.intake import issue_point_report
from tests.support import LedgerCase


def _repack(encoded, **fields):
    wire = json.loads(encoded)
    wire['body'].update(fields)
    payload = json.dumps(wire['body'], sort_keys=True, separators=(',', ':')).encode('ascii')
    wire['piece_id'] = 'point-' + hashlib.sha256(payload).hexdigest()
    return json.dumps(wire, sort_keys=True, separators=(',', ':')).encode('ascii')


class ReplayTests(LedgerCase):
    def test_closed_source_replay(self):
        front, rear = self.safe_pair()
        self.station.close()
        report = issue_point_report(self.center, front.encoded, rear.encoded)
        self.assertEqual((report.body.stop_beat, report.body.exit_load), (None, 4))
        self.assertEqual(report.body.plan_id, front.plan.plan_id)
        self.assertEqual(tuple(parent.piece_id for parent in report.body.parents), (front.piece_id, rear.piece_id))
        self.assertEqual(tuple(parent.revision_id for parent in report.body.parents), (front.revision_id, rear.revision_id))
        self.assertEqual(report.receipt.report_id, report.report_id)
        self.assertEqual(read_point_report(self.center, report.report_id), report)
        self.assertEqual(self.archive_counts(), (1, 1))

    def test_wrong_point_handoff(self):
        front, rear = self.safe_pair()
        wrong = issue_point(self.station, rear.revision_id, 1)
        self.station.close()
        with self.assertRaisesRegex(ValueError, 'rear point entry'):
            issue_point_report(self.center, front, wrong)
        self.assertEqual(self.archive_counts(), (0, 0))

    def test_foreign_plan(self):
        front, _ = self.safe_pair()
        foreign = self.make_plan(batch='LOT-B')
        revision = self.freeze(foreign, 'rear', [('r1', 2, 'ok')])
        rear = issue_point(self.station, revision, 2)
        self.station.close()
        with self.assertRaisesRegex(ValueError, 'same fixed plan'):
            issue_point_report(self.center, front, rear)
        self.assertEqual(self.archive_counts(), (0, 0))

    def test_bad_piece(self):
        front, rear = self.safe_pair()
        stop_revision = self.freeze(front.plan.plan_id, 'front', [('p1', 4, 'ok')])
        stopped = issue_point(self.station, stop_revision, 1)
        self.station.close()
        for bad in (
            _repack(front.encoded, version=2),
            _repack(front.encoded, version=True),
            front.encoded[:-3],
            _repack(stopped.encoded, exit_load='0'),
            _repack(front.encoded, revision_id=rear.revision_id),
            front.encoded.replace(b'"exit_load":"2"', b'"exit_load":"3"'),
            replace(front, exit_load=3),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    issue_point_report(self.center, bad, rear)
        with self.assertRaises(ValueError):
            issue_point_report(self.center, stopped, rear.encoded[:-1])
        self.assertEqual(self.archive_counts(), (0, 0))

    def test_order(self):
        front, rear = self.safe_pair()
        self.station.close()
        for first, second in ((rear, front), (front, front), (rear, rear)):
            with self.assertRaisesRegex(ValueError, 'in order'):
                issue_point_report(self.center, first, second)
        self.assertEqual(self.archive_counts(), (0, 0))

    def test_rear_stop(self):
        front, rear = self.safe_pair()
        revision = self.freeze(front.plan.plan_id, 'rear', [('r1', 3, 'ok')], rear.revision_id)
        stopped = issue_point(self.station, revision, 2)
        self.station.close()
        report = issue_point_report(self.center, front, stopped)
        self.assertEqual((report.body.stop_beat, report.body.exit_load), ('r1', None))
        self.assertEqual(report.body.parents[1].revision_id, revision)

    def test_front_stop(self):
        plan_id = self.make_plan()
        front_revision = self.freeze(plan_id, 'front', [('p1', 3, 'ok')])
        rear_revision = self.freeze(plan_id, 'rear', [('r1', 2, 'ok')])
        front = issue_point(self.station, front_revision, 2)
        rear = issue_point(self.station, rear_revision, 1)
        self.station.close()
        report = issue_point_report(self.center, front, rear)
        self.assertEqual((report.body.stop_beat, report.body.exit_load), ('p1', None))
        self.assertEqual(tuple(parent.revision_id for parent in report.body.parents), (front_revision, rear_revision))
        self.assertEqual(report.body.parents[1].entry, 1)

    def test_observation_to_first_stop(self):
        plan_id = self.make_plan(front=('p1', 'p2', 'p3'))
        with self.assertRaisesRegex(ValueError, 'quality'):
            self.freeze(plan_id, 'front', [('p3', 2, 'suspect'), ('p2', 3, 'ok'), ('p1', -3, 'ok')])
        self.assertEqual(self.revision_count(), 0)
        front_id = self.freeze(plan_id, 'front', [('p3', 2, 'ok'), ('p2', 3, 'ok'), ('p1', -3, 'ok')])
        rear_id = self.freeze(plan_id, 'rear', [('r1', 1, 'ok')])
        front = issue_point(self.station, front_id, 2)
        rear = issue_point(self.station, rear_id, 0)
        self.station.close()
        self.assertEqual((front.stop_beat, front.exit_load), ('p3', None))
        report = issue_point_report(self.center, front, rear)
        self.assertEqual((report.body.stop_beat, report.body.exit_load), ('p3', None))
        self.assertEqual(report.body.parents[0].revision_id, front_id)

    def test_closed_source_parent_choices(self):
        safe, _ = self.safe_pair()
        plan_id = safe.plan.plan_id
        stop_revision = self.freeze(plan_id, 'front', [('p1', 3, 'ok')], safe.revision_id)
        stopped = issue_point(self.station, stop_revision, 2)
        rear_revision = self.freeze(plan_id, 'rear', [('r1', 1, 'ok')])
        early_entry = issue_point(self.station, rear_revision, 1)
        safe_entry = issue_point(self.station, rear_revision, 2)
        other_id = self.make_plan(batch='LOT-B')
        other_revision = self.freeze(other_id, 'rear', [('r1', 1, 'ok')])
        other = issue_point(self.station, other_revision, 2)
        self.station.close()
        self.assertNotEqual(early_entry.piece_id, safe_entry.piece_id)
        self.assertEqual(issue_point_report(self.center, safe, safe_entry).body.exit_load, 3)
        for rejected in (early_entry, other):
            with self.assertRaises(ValueError):
                issue_point_report(self.center, safe, rejected)
        report = issue_point_report(self.center, stopped, early_entry)
        self.assertEqual((report.body.stop_beat, report.body.exit_load), ('p1', None))
        self.assertEqual(report.body.parents[1].piece_id, early_entry.piece_id)
        self.assertEqual(self.archive_counts(), (2, 2))
