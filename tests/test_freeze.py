from decimal import Decimal
from fractions import Fraction

from plans.catalog import read_plan_record, register_plan
from source.freezes import read_frozen_revision
from tests.support import LedgerCase


class FreezeTests(LedgerCase):
    def test_complete_revision(self):
        plan_id = self.make_plan(front=('p1', 'p2'))
        revision_id = self.freeze(plan_id, 'front', [('p1', 1, 'ok'), ('p2', -2, 'ok')])
        revision = read_frozen_revision(self.station, revision_id)
        self.assertEqual(revision.revision_id, revision_id)
        self.assertEqual((revision.plan_id, revision.segment, revision.sequence), (plan_id, 'front', 1))
        self.assertIsNone(revision.previous_revision_id)
        self.assertEqual([(row.beat, row.reading) for row in revision.observations], [('p1', 1), ('p2', -2)])
        self.assertEqual(self.revision_count(), 1)

    def test_missing_slot(self):
        plan_id = self.make_plan(front=('p1', 'p2'))
        with self.assertRaisesRegex(ValueError, 'missing observations'):
            self.freeze(plan_id, 'front', [('p1', 1, 'ok')])
        self.assertEqual(self.revision_count(), 0)

    def test_plan_registration(self):
        plan_id = self.make_plan(limit='5.0', calibration=('2/2', Decimal('0.00')))
        self.assertEqual(self.make_plan(), plan_id)
        original = read_plan_record(self.station, plan_id)
        for segments, calibration, limit in (
            ([('front', ('p1',)), ('rear', ('p1',))], (1, 0), 5),
            ([('front', ('p1',)), ('front', ('r1',))], (1, 0), 5),
            ([('front', ()), ('rear', ('r1',))], (1, 0), 5),
            ([('front', ('p1',)), ('rear', ('r1',))], (0, 0), 5),
            ([('front', ('p1',)), ('rear', ('r1',))], (1, None), 5),
            ([('front', ('p1',)), ('rear', ('r1',))], (1, 0), 0),
            ([('front', ('p1',)), ('rear', ('r1',))], (1, 0), 'Infinity'),
        ):
            with self.subTest(segments=segments, calibration=calibration, limit=limit):
                with self.assertRaises(ValueError):
                    register_plan(self.station, 'INVALID', segments, calibration, limit)
        with self.assertRaisesRegex(ValueError, 'conflicting registration'):
            self.make_plan(limit=6)
        self.assertEqual(read_plan_record(self.station, plan_id), original)
        self.assertEqual(self.station.execute('SELECT COUNT(*) FROM plans').fetchone()[0], 1)

    def test_named_order(self):
        plan_id = self.make_plan(front=('p1', 'p2', 'p3'))
        revision_id = self.freeze(
            plan_id, 'front', [('p3', 2, 'ok'), ('p2', '3/2', 'ok'), ('p1', -3, 'ok')]
        )
        rows = read_frozen_revision(self.station, revision_id).observations
        self.assertEqual([(row.beat, row.reading) for row in rows], [('p1', -3), ('p2', Fraction(3, 2)), ('p3', 2)])

    def test_amendment(self):
        plan_id = self.make_plan(front=('p1', 'p2'))
        old = self.freeze(plan_id, 'front', [('p1', 1, 'ok'), ('p2', 2, 'ok')])
        new = self.freeze(plan_id, 'front', [('p2', 2, 'ok'), ('p1', 3, 'ok')], old)
        before = read_frozen_revision(self.station, old)
        after = read_frozen_revision(self.station, new)
        self.assertNotEqual(old, new)
        self.assertEqual((before.sequence, after.sequence, after.previous_revision_id), (1, 2, old))
        self.assertEqual([row.reading for row in before.observations], [1, 2])
        self.assertEqual([row.reading for row in after.observations], [3, 2])
        self.assertEqual(self.revision_count(), 2)

    def test_reopen_station(self):
        plan_id = self.make_plan()
        original = self.freeze(plan_id, 'front', [('p1', 1, 'ok')])
        amendment = self.freeze(plan_id, 'front', [('p1', 3, 'ok')], original)
        self.station.close()
        self.open_station()
        self.assertEqual(self.make_plan(), plan_id)
        self.assertEqual(read_plan_record(self.station, plan_id).stop_limit, 5)
        self.assertEqual(read_frozen_revision(self.station, original).observations[0].reading, 1)
        reopened = read_frozen_revision(self.station, amendment)
        self.assertEqual((reopened.previous_revision_id, reopened.observations[0].reading), (original, 3))
        third = self.freeze(plan_id, 'front', [('p1', 4, 'ok')], amendment)
        self.assertEqual(read_frozen_revision(self.station, third).sequence, 3)
        self.assertEqual(self.revision_count(), 3)

    def test_quality(self):
        plan_id = self.make_plan(front=('p1', 'p2'))
        for reading, quality in ((2, 'suspect'), (None, 'ok'), ('', 'ok'), (Decimal('NaN'), 'ok'), ('Inf', 'ok')):
            with self.subTest(reading=reading, quality=quality):
                with self.assertRaises(ValueError):
                    self.freeze(plan_id, 'front', [('p1', 1, 'ok'), ('p2', reading, quality)])
                self.assertEqual(self.revision_count(), 0)

    def test_roster(self):
        plan_id = self.make_plan(front=('p1', 'p2'))
        other_plan = self.make_plan(batch='LOT-B')
        rear = self.freeze(plan_id, 'rear', [('r1', 0, 'ok')])
        other_front = self.freeze(other_plan, 'front', [('p1', 0, 'ok')])
        complete = [('p1', 1, 'ok'), ('p2', 2, 'ok')]
        for segment, rows, previous in (
            ('front', [complete[0], complete[0]], None),
            ('front', [complete[0], ('r1', 2, 'ok')], None),
            ('no-such-segment', complete, None),
            ('front', complete, rear),
            ('front', complete, other_front),
            ('front', complete, 'unknown-revision'),
        ):
            with self.subTest(segment=segment, rows=rows, previous=previous):
                with self.assertRaises(ValueError):
                    self.freeze(plan_id, segment, rows, previous)
                self.assertEqual(self.revision_count(), 2)
        with self.assertRaises(KeyError):
            self.freeze('unknown-plan', 'front', complete)
        self.assertEqual(self.revision_count(), 2)
