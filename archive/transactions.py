import sqlite3

from archive.receipts import (
    encode_point_receipt,
    encode_range_receipt,
    make_point_receipt,
    make_range_receipt,
)
from archive.reports import (
    PointReport,
    PointReportBody,
    RangeReport,
    RangeReportBody,
    encode_range_report_body,
    encode_report_body,
)
from archive.store import (
    insert_range_report_body,
    insert_range_report_receipt,
    insert_report_body,
    insert_report_receipt,
)


def commit_point_report(db: sqlite3.Connection, body: PointReportBody) -> PointReport:
    encoded_body = encode_report_body(body)
    db.execute('BEGIN IMMEDIATE')
    try:
        report_id = insert_report_body(db, encoded_body)
        receipt = make_point_receipt(report_id)
        insert_report_receipt(db, report_id, receipt.receipt_id, encode_point_receipt(receipt))
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return PointReport(report_id, body, receipt)


def commit_range_report(db: sqlite3.Connection, body: RangeReportBody) -> RangeReport:
    encoded_body = encode_range_report_body(body)
    db.execute('BEGIN IMMEDIATE')
    try:
        report_id = insert_range_report_body(db, encoded_body)
        receipt = make_range_receipt(report_id)
        insert_range_report_receipt(
            db, report_id, receipt.receipt_id, encode_range_receipt(receipt)
        )
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return RangeReport(report_id, body, receipt)
