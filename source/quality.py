from fractions import Fraction

from plans.units import normalize_rational


def validate_observation_quality(quality: object) -> None:
    if not isinstance(quality, str) or quality != 'ok':
        raise ValueError('observation quality must be ok')


def validate_observed_reading(reading: object, quality: object) -> Fraction:
    validate_observation_quality(quality)
    return normalize_rational(reading, 'observed reading')
