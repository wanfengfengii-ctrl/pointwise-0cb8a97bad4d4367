import sqlite3


def initialize_archive_store(db: sqlite3.Connection) -> None:
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('''
        CREATE TABLE IF NOT EXISTS point_reports (
            report_id INTEGER PRIMARY KEY,
            body TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS point_report_receipts (
            report_id INTEGER PRIMARY KEY REFERENCES point_reports (report_id),
            receipt_id TEXT NOT NULL UNIQUE,
            receipt TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS range_reports (
            report_id INTEGER PRIMARY KEY,
            body TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS range_report_receipts (
            report_id INTEGER PRIMARY KEY REFERENCES range_reports (report_id),
            receipt_id TEXT NOT NULL UNIQUE,
            receipt TEXT NOT NULL
        )
    ''')


def insert_report_body(db: sqlite3.Connection, encoded: str) -> int:
    cursor = db.execute('INSERT INTO point_reports (body) VALUES (?)', (encoded,))
    return cursor.lastrowid


def insert_report_receipt(
    db: sqlite3.Connection, report_id: int, receipt_id: str, encoded: str
) -> None:
    db.execute(
        'INSERT INTO point_report_receipts (report_id, receipt_id, receipt) VALUES (?, ?, ?)',
        (report_id, receipt_id, encoded),
    )


def load_report_with_receipt(db: sqlite3.Connection, report_id: int) -> tuple[str, str]:
    if type(report_id) is not int or report_id <= 0 or report_id > 2**63 - 1:
        raise KeyError(report_id)
    row = db.execute(
        'SELECT point_reports.body, point_report_receipts.receipt FROM point_reports '
        'JOIN point_report_receipts USING (report_id) WHERE report_id = ?',
        (report_id,),
    ).fetchone()
    if row is None:
        raise KeyError(report_id)
    return row[0], row[1]


def insert_range_report_body(db: sqlite3.Connection, encoded: str) -> int:
    cursor = db.execute('INSERT INTO range_reports (body) VALUES (?)', (encoded,))
    return cursor.lastrowid


def insert_range_report_receipt(
    db: sqlite3.Connection, report_id: int, receipt_id: str, encoded: str
) -> None:
    db.execute(
        'INSERT INTO range_report_receipts (report_id, receipt_id, receipt) VALUES (?, ?, ?)',
        (report_id, receipt_id, encoded),
    )


def load_range_report_with_receipt(db: sqlite3.Connection, report_id: int) -> tuple[str, str]:
    if type(report_id) is not int or report_id <= 0 or report_id > 2**63 - 1:
        raise KeyError(report_id)
    row = db.execute(
        'SELECT range_reports.body, range_report_receipts.receipt FROM range_reports '
        'JOIN range_report_receipts USING (report_id) WHERE report_id = ?',
        (report_id,),
    ).fetchone()
    if row is None:
        raise KeyError(report_id)
    return row[0], row[1]
