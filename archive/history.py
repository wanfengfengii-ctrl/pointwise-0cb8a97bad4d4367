from archive.receipts import decode_point_receipt
from archive.reports import PointReport, decode_report_body
from archive.store import load_report_with_receipt


def read_point_report(db, report_id: int) -> PointReport:
    stored_body, stored_receipt = load_report_with_receipt(db, report_id)
    receipt = decode_point_receipt(stored_receipt)
    if receipt.report_id != report_id:
        raise ValueError('stored receipt belongs to a different report')
    return PointReport(report_id, decode_report_body(stored_body), receipt)
