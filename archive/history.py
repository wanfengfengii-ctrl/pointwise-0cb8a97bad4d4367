from archive.receipts import decode_point_receipt, decode_range_receipt
from archive.reports import (
    PointReport,
    RangeReport,
    decode_range_report_body,
    decode_report_body,
)
from archive.store import load_range_report_with_receipt, load_report_with_receipt


def read_point_report(db, report_id: int) -> PointReport:
    stored_body, stored_receipt = load_report_with_receipt(db, report_id)
    receipt = decode_point_receipt(stored_receipt)
    if receipt.report_id != report_id:
        raise ValueError('stored receipt belongs to a different report')
    return PointReport(report_id, decode_report_body(stored_body), receipt)


def read_range_report(db, report_id: int) -> RangeReport:
    stored_body, stored_receipt = load_range_report_with_receipt(db, report_id)
    receipt = decode_range_receipt(stored_receipt)
    if receipt.report_id != report_id:
        raise ValueError('stored receipt belongs to a different report')
    return RangeReport(report_id, decode_range_report_body(stored_body), receipt)
