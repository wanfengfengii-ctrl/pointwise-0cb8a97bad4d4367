from dataclasses import dataclass

from plans.segments import SegmentRoster, normalize_label
from source.quality import validate_observed_reading


@dataclass(frozen=True)
class Observation:
    beat: str
    reading: object
    quality: str


def order_complete_observations(
    roster: SegmentRoster, observations
) -> tuple[Observation, ...]:
    try:
        rows = iter(observations)
    except TypeError as exc:
        raise ValueError('observations must be iterable') from exc

    expected = set(roster.beats)
    by_beat = {}
    for row in rows:
        if not isinstance(row, Observation):
            raise ValueError('each row must be an Observation')
        beat = normalize_label(row.beat, 'observed beat')
        if beat not in expected:
            raise ValueError(f'beat {beat!r} is outside segment {roster.name!r}')
        if beat in by_beat:
            raise ValueError(f'duplicate observation for {beat!r}')
        reading = validate_observed_reading(row.reading, row.quality)
        by_beat[beat] = Observation(beat, reading, row.quality)

    missing = [beat for beat in roster.beats if beat not in by_beat]
    if missing:
        raise ValueError(f'missing observations for {missing!r}')
    return tuple(by_beat[beat] for beat in roster.beats)
