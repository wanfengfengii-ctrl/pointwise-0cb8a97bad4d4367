import sqlite3


def initialize_piece_store(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS point_pieces (
            revision_id TEXT NOT NULL REFERENCES observation_revisions (revision_id),
            entry TEXT NOT NULL,
            piece_id TEXT NOT NULL UNIQUE,
            encoded BLOB NOT NULL,
            PRIMARY KEY (revision_id, entry)
        )
    ''')


def find_issued_piece(db: sqlite3.Connection, revision_id: str, entry: str) -> bytes | None:
    row = db.execute(
        'SELECT encoded FROM point_pieces WHERE revision_id = ? AND entry = ?',
        (revision_id, entry),
    ).fetchone()
    return row[0] if row is not None else None


def save_or_get_issued_piece(
    db: sqlite3.Connection, revision_id: str, entry: str, piece_id: str, encoded: bytes
) -> bytes:
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute(
            'INSERT INTO point_pieces (revision_id, entry, piece_id, encoded) VALUES (?, ?, ?, ?) '
            'ON CONFLICT (revision_id, entry) DO NOTHING',
            (revision_id, entry, piece_id, encoded),
        )
        fixed = find_issued_piece(db, revision_id, entry)
        if fixed is None:
            raise RuntimeError('issued station piece was not stored')
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return fixed
