import sqlite3
import tempfile
import unittest
from pathlib import Path

from archive.store import initialize_archive_store
from issuer.pieces import issue_point
from issuer.store import initialize_piece_store
from plans.catalog import register_plan
from plans.store import initialize_plan_store
from source.freezes import freeze_observations
from source.observations import Observation
from source.store import initialize_observation_store


class LedgerCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='coating-tests-')
        self.addCleanup(folder.cleanup)
        self.station_path = Path(folder.name) / 'station.sqlite3'
        self.center_path = Path(folder.name) / 'center.sqlite3'
        self.open_station()
        self.open_center()

    def open_station(self):
        self.station = sqlite3.connect(self.station_path)
        self.addCleanup(self.station.close)
        initialize_plan_store(self.station)
        initialize_observation_store(self.station)
        initialize_piece_store(self.station)

    def open_center(self):
        self.center = sqlite3.connect(self.center_path)
        self.addCleanup(self.center.close)
        initialize_archive_store(self.center)

    def make_plan(self, batch='LOT-A', front=('p1',), rear=('r1',), limit=5, calibration=(1, 0)):
        return register_plan(
            self.station, batch, [('front', front), ('rear', rear)], calibration, limit
        )

    def freeze(self, plan_id, segment, rows, previous=None):
        observations = [Observation(*row) for row in rows]
        return freeze_observations(self.station, plan_id, segment, observations, previous)

    def safe_pair(self):
        plan_id = self.make_plan()
        front_id = self.freeze(plan_id, 'front', [('p1', 1, 'ok')])
        rear_id = self.freeze(plan_id, 'rear', [('r1', 2, 'ok')])
        front = issue_point(self.station, front_id, 1)
        rear = issue_point(self.station, rear_id, front.exit_load)
        return front, rear

    def revision_count(self):
        return self.station.execute('SELECT COUNT(*) FROM observation_revisions').fetchone()[0]

    def piece_count(self):
        return self.station.execute('SELECT COUNT(*) FROM point_pieces').fetchone()[0]

    def archive_counts(self):
        return self.center.execute(
            'SELECT (SELECT COUNT(*) FROM point_reports), '
            '(SELECT COUNT(*) FROM point_report_receipts)'
        ).fetchone()
