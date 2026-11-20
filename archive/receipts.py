import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PointReceipt:
    report_id: int
    receipt_id: str


def make_point_receipt(report_id: int) -> PointReceipt:
    return PointReceipt(report_id, f'point-receipt-{report_id}')


def encode_point_receipt(receipt: PointReceipt) -> str:
    return json.dumps(
        {'report_id': receipt.report_id, 'receipt_id': receipt.receipt_id},
        sort_keys=True,
        separators=(',', ':'),
    )


def decode_point_receipt(encoded: str) -> PointReceipt:
    fields = json.loads(encoded)
    report_id = fields['report_id']
    if type(report_id) is not int or report_id <= 0:
        raise ValueError('invalid receipt report identity')
    receipt = make_point_receipt(report_id)
    if encode_point_receipt(receipt) != encoded:
        raise ValueError('stored receipt identity mismatch')
    return receipt


@dataclass(frozen=True)
class RangeReceipt:
    report_id: int
    receipt_id: str


def make_range_receipt(report_id: int) -> RangeReceipt:
    return RangeReceipt(report_id, f'range-receipt-{report_id}')


def encode_range_receipt(receipt: RangeReceipt) -> str:
    return json.dumps(
        {'report_id': receipt.report_id, 'receipt_id': receipt.receipt_id},
        sort_keys=True,
        separators=(',', ':'),
    )


def decode_range_receipt(encoded: str) -> RangeReceipt:
    fields = json.loads(encoded)
    report_id = fields['report_id']
    if type(report_id) is not int or report_id <= 0:
        raise ValueError('invalid receipt report identity')
    receipt = make_range_receipt(report_id)
    if encode_range_receipt(receipt) != encoded:
        raise ValueError('stored receipt identity mismatch')
    return receipt
