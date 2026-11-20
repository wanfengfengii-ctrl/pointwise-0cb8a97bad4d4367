from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentRoster:
    name: str
    beats: tuple[str, ...]
    position: int


def normalize_label(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty name')
    return value.strip()


def normalize_segments(segments) -> tuple[SegmentRoster, SegmentRoster]:
    if not isinstance(segments, (list, tuple)) or len(segments) != 2:
        raise ValueError('a plan requires two ordered segments')

    rosters = []
    segment_names = set()
    beat_names = set()
    for position, item in enumerate(segments):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError('each segment requires a name and beat roster')
        name = normalize_label(item[0], 'segment')
        if name in segment_names:
            raise ValueError(f'duplicate segment {name!r}')
        segment_names.add(name)
        if not isinstance(item[1], (list, tuple)) or not item[1]:
            raise ValueError(f'segment {name!r} requires a nonempty beat roster')
        beats = []
        for value in item[1]:
            beat = normalize_label(value, 'beat')
            if beat in beat_names:
                raise ValueError(f'duplicate plan beat {beat!r}')
            beat_names.add(beat)
            beats.append(beat)
        rosters.append(SegmentRoster(name, tuple(beats), position))
    return rosters[0], rosters[1]


def find_segment_roster(segments, name: str) -> SegmentRoster:
    name = normalize_label(name, 'segment')
    for roster in segments:
        if roster.name == name:
            return roster
    raise ValueError(f'segment {name!r} is outside the plan')
