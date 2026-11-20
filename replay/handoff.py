from replay.selection import PointParents


def require_point_handoff(parents: PointParents) -> None:
    if parents.front.exit_load != parents.rear.entry:
        raise ValueError('rear point entry differs from the front safe exit')
