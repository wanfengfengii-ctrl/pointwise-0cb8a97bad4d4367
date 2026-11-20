import sqlite3

from archive.history import read_point_report
from issuer.pieces import issue_point
from replay.intake import issue_point_report
from tests.support import LedgerCase


def _reject_receipt_write(db):
    db.execute('''
        CREATE TEMP TRIGGER reject_receipt
        BEFORE INSERT ON point_report_receipts
        WHEN EXISTS (SELECT 1 FROM point_reports WHERE report_id = NEW.report_id)
        BEGIN
            SELECT RAISE(ABORT, 'receipt rejected after report write');
        END
    ''')


class ArchiveTests(LedgerCase):
    def test_rejected_commit_and_retry(self):
        front, rear = self.safe_pair()
        self.station.close()
        self.center.execute('''
            CREATE TABLE test_commit_guard (
                parent_id INTEGER REFERENCES point_reports(report_id)
                    DEFERRABLE INITIALLY DEFERRED
            )
        ''')
        self.center.execute('''
            CREATE TEMP TRIGGER reject_commit
            AFTER INSERT ON point_report_receipts
            BEGIN
                INSERT INTO test_commit_guard (parent_id) VALUES (-1);
            END
        ''')
        with self.assertRaises(sqlite3.IntegrityError) as raised:
            issue_point_report(self.center, front, rear)
        self.assertEqual(raised.exception.sqlite_errorname, 'SQLITE_CONSTRAINT_FOREIGNKEY')
        self.assertFalse(self.center.in_transaction)
        self.assertEqual(self.archive_counts(), (0, 0))
        self.assertEqual(self.center.execute('SELECT COUNT(*) FROM test_commit_guard').fetchone()[0], 0)
        self.center.execute('DROP TRIGGER reject_commit')
        report = issue_point_report(self.center, front, rear)
        self.assertEqual(self.archive_counts(), (1, 1))
        self.assertEqual(read_point_report(self.center, report.report_id), report)

    def test_after_report_write(self):
        front, rear = self.safe_pair()
        self.station.close()
        _reject_receipt_write(self.center)
        with self.assertRaises(sqlite3.IntegrityError) as raised:
            issue_point_report(self.center, front, rear)
        self.assertEqual(raised.exception.args, ('receipt rejected after report write',))
        self.assertEqual(raised.exception.sqlite_errorname, 'SQLITE_CONSTRAINT_TRIGGER')
        self.assertFalse(self.center.in_transaction)
        self.center.close()
        self.open_center()
        self.assertEqual(self.archive_counts(), (0, 0))
        report = issue_point_report(self.center, front, rear)
        self.assertEqual(self.archive_counts(), (1, 1))
        self.assertEqual(read_point_report(self.center, report.report_id), report)

    def test_read_after_amendment(self):
        front, rear = self.safe_pair()
        signed = issue_point_report(self.center, front, rear)
        amendment = self.freeze(front.plan.plan_id, 'front', [('p1', 3, 'ok')], front.revision_id)
        self.assertNotEqual(issue_point(self.station, amendment, 1).piece_id, front.piece_id)
        self.station.close()
        self.center.close()
        self.open_center()
        self.assertEqual(read_point_report(self.center, signed.report_id), signed)
        self.assertEqual(signed.body.exit_load, 4)
        self.assertEqual(signed.body.parents[0].revision_id, front.revision_id)

    def test_original_parent(self):
        front, rear = self.safe_pair()
        original = issue_point_report(self.center, front, rear)
        new_revision = self.freeze(front.plan.plan_id, 'front', [('p1', 3, 'ok')], front.revision_id)
        self.station.close()
        self.open_station()
        old_at_two = issue_point(self.station, front.revision_id, 2)
        new_at_two = issue_point(self.station, new_revision, 2)
        self.assertEqual((old_at_two.stop_beat, old_at_two.exit_load), (None, 3))
        self.assertEqual((new_at_two.stop_beat, new_at_two.exit_load), ('p1', None))
        self.station.close()

        _reject_receipt_write(self.center)
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'receipt rejected after report write'):
            issue_point_report(self.center, new_at_two, rear)
        self.center.close()
        self.open_center()
        self.assertEqual(self.archive_counts(), (1, 1))
        current = issue_point_report(self.center, new_at_two, rear)
        self.assertNotEqual(current.report_id, original.report_id)
        self.center.close()
        self.open_center()

        old_stored = read_point_report(self.center, original.report_id)
        new_stored = read_point_report(self.center, current.report_id)
        self.assertEqual(old_stored, original)
        self.assertEqual(new_stored, current)
        self.assertEqual((old_stored.body.stop_beat, old_stored.body.exit_load), (None, 4))
        self.assertEqual((new_stored.body.stop_beat, new_stored.body.exit_load), ('p1', None))
        self.assertEqual(tuple(parent.piece_id for parent in old_stored.body.parents), (front.piece_id, rear.piece_id))
        self.assertEqual(tuple(parent.piece_id for parent in new_stored.body.parents), (new_at_two.piece_id, rear.piece_id))
        self.assertEqual(tuple(parent.revision_id for parent in new_stored.body.parents), (new_revision, rear.revision_id))
        self.assertEqual((old_stored.receipt.report_id, new_stored.receipt.report_id), (original.report_id, current.report_id))
        self.assertEqual(self.archive_counts(), (2, 2))

    def test_unknown_report(self):
        front, rear = self.safe_pair()
        self.station.close()
        signed = issue_point_report(self.center, front, rear)
        with self.assertRaises(KeyError) as raised:
            read_point_report(self.center, signed.report_id + 1)
        self.assertEqual(raised.exception.args, (signed.report_id + 1,))
        self.assertEqual(self.archive_counts(), (1, 1))
