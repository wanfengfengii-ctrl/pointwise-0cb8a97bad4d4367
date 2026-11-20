from fractions import Fraction

from plans.units import normalize_rational


def normalize_stop_limit(value: object) -> Fraction:
    limit = normalize_rational(value, 'stop limit')
    if limit <= 0:
        raise ValueError('stop limit must be positive')
    return limit


def validate_safe_load(value: object, limit: Fraction, field: str = 'entry') -> Fraction:
    load = normalize_rational(value, field)
    if not 0 <= load < limit:
        raise ValueError(f'{field} must be in [0, {limit})')
    return load
