from decimal import Decimal
from fractions import Fraction

from issuer.codec import decode_point_piece, encode_point_piece
from issuer.pieces import issue_point
from tests.support import LedgerCase


class IssueTests(LedgerCase):
    def test_floor_and_repeat(self):
        plan_id = self.make_plan(front=('p1', 'p2'))
        revision = self.freeze(plan_id, 'front', [('p1', -2, 'ok'), ('p2', 1, 'ok')])
        piece = issue_point(self.station, revision, 1)
        duplicate = issue_point(self.station, revision, 1)
        self.assertEqual((piece.stop_beat, piece.exit_load), (None, Fraction(1)))
        self.assertEqual((duplicate.piece_id, duplicate.encoded), (piece.piece_id, piece.encoded))
        self.assertEqual(self.piece_count(), 1)

    def test_equality_is_stop(self):
        plan_id = self.make_plan()
        revision = self.freeze(plan_id, 'front', [('p1', 3, 'ok')])
        piece = issue_point(self.station, revision, 2)
        self.assertEqual((piece.stop_beat, piece.exit_load), ('p1', None))

    def test_entry_identity(self):
        plan_id = self.make_plan()
        revision = self.freeze(plan_id, 'front', [('p1', 1, 'ok')])
        one = issue_point(self.station, revision, 1)
        two = issue_point(self.station, revision, 2)
        self.assertNotEqual(one.piece_id, two.piece_id)
        self.assertEqual((one.entry, one.exit_load, two.entry, two.exit_load), (1, 2, 2, 3))
        self.assertEqual(issue_point(self.station, revision, '2/2'), one)
        self.station.close()
        self.open_station()
        self.assertEqual(issue_point(self.station, revision, Decimal('1.00')).encoded, one.encoded)
        self.assertEqual(issue_point(self.station, revision, 2).encoded, two.encoded)
        self.assertEqual(self.piece_count(), 2)

    def test_entry_bounds(self):
        plan_id = self.make_plan()
        revision = self.freeze(plan_id, 'front', [('p1', 1, 'ok')])
        self.assertEqual(issue_point(self.station, revision, 0).exit_load, 1)
        for entry in (-1, 5, None, True, 'not a number', '1/0', Decimal('Infinity')):
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError):
                    issue_point(self.station, revision, entry)
        with self.assertRaises(KeyError):
            issue_point(self.station, 'unknown', 0)
        self.assertEqual(self.piece_count(), 1)

    def test_calibrated_rationals(self):
        plan_id = self.make_plan(limit=1, calibration=('1/3', '1/6'))
        revision = self.freeze(plan_id, 'front', [('p1', 1, 'ok')])
        piece = issue_point(self.station, revision, '1/2')
        self.assertEqual((piece.entry, piece.stop_beat, piece.exit_load), (Fraction(1, 2), 'p1', None))
        self.assertEqual(decode_point_piece(piece.encoded), piece)
        self.assertEqual(piece.encoded, encode_point_piece(piece.plan, 'front', revision, '0.50', 'p1', None))
        below = issue_point(self.station, revision, '1/3')
        self.assertEqual((below.stop_beat, below.exit_load), (None, Fraction(5, 6)))

    def test_first_stop(self):
        plan_id = self.make_plan(front=('p1', 'p2'))
        revision = self.freeze(plan_id, 'front', [('p1', 3, 'ok'), ('p2', -4, 'ok')])
        piece = issue_point(self.station, revision, 2)
        self.assertEqual((piece.stop_beat, piece.exit_load), ('p1', None))
