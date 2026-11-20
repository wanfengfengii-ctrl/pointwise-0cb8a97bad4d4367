from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction


@dataclass(frozen=True)
class CalibrationSpec:
    multiplier: Fraction
    offset: Fraction


def normalize_rational(value: object, field: str = 'value') -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, Fraction, Decimal, str)):
        raise ValueError(f'{field} requires an exact rational value')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f'{field} requires a finite rational value') from exc


def encode_rational(value: Fraction) -> str:
    return str(value)


def normalize_calibration(calibration) -> CalibrationSpec:
    if isinstance(calibration, CalibrationSpec):
        multiplier, offset = calibration.multiplier, calibration.offset
    elif isinstance(calibration, (list, tuple)) and len(calibration) == 2:
        multiplier, offset = calibration
    else:
        raise ValueError('calibration requires multiplier and offset')
    multiplier = normalize_rational(multiplier, 'multiplier')
    offset = normalize_rational(offset, 'offset')
    if multiplier <= 0:
        raise ValueError('multiplier must be positive')
    return CalibrationSpec(multiplier, offset)
