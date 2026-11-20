import sqlite3

from source.revisions import build_observation_revision, encode_observation_revision


def initialize_observation_store(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS observation_revisions (
            revision_id TEXT PRIMARY KEY NOT NULL,
            plan_id TEXT NOT NULL REFERENCES plans (plan_id),
            segment TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK (sequence > 0),
            previous_revision_id TEXT REFERENCES observation_revisions (revision_id),
            snapshot TEXT NOT NULL,
            UNIQUE (plan_id, segment, sequence)
        )
    ''')


def append_revision_snapshot(db: sqlite3.Connection, plan_id, roster, previous_id, observations) -> str:
    db.execute('BEGIN IMMEDIATE')
    try:
        sequence = db.execute(
            'SELECT COALESCE(MAX(sequence), 0) + 1 FROM observation_revisions '
            'WHERE plan_id = ? AND segment = ?',
            (plan_id, roster.name),
        ).fetchone()[0]
        revision = build_observation_revision(
            plan_id, roster.name, roster.position, sequence, previous_id, observations
        )
        db.execute(
            'INSERT INTO observation_revisions '
            '(revision_id, plan_id, segment, sequence, previous_revision_id, snapshot) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (
                revision.revision_id, plan_id, roster.name, sequence, previous_id,
                encode_observation_revision(revision),
            ),
        )
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return revision.revision_id


def load_revision_snapshot(db: sqlite3.Connection, revision_id: str) -> str:
    if not isinstance(revision_id, str):
        raise KeyError(revision_id)
    row = db.execute(
        'SELECT snapshot FROM observation_revisions WHERE revision_id = ?', (revision_id,)
    ).fetchone()
    if row is None:
        raise KeyError(revision_id)
    return row[0]
