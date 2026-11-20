import sqlite3


def initialize_plan_store(db: sqlite3.Connection) -> None:
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('''
        CREATE TABLE IF NOT EXISTS plans (
            plan_id TEXT PRIMARY KEY NOT NULL,
            snapshot TEXT NOT NULL
        )
    ''')


def save_plan_snapshot(db: sqlite3.Connection, plan_id: str, snapshot: str) -> None:
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute(
            'INSERT INTO plans (plan_id, snapshot) VALUES (?, ?) '
            'ON CONFLICT (plan_id) DO NOTHING',
            (plan_id, snapshot),
        )
        if load_plan_snapshot(db, plan_id) != snapshot:
            raise ValueError(f'conflicting registration for {plan_id}')
        db.commit()
    except BaseException:
        db.rollback()
        raise


def load_plan_snapshot(db: sqlite3.Connection, plan_id: str) -> str:
    if not isinstance(plan_id, str):
        raise KeyError(plan_id)
    row = db.execute('SELECT snapshot FROM plans WHERE plan_id = ?', (plan_id,)).fetchone()
    if row is None:
        raise KeyError(plan_id)
    return row[0]
