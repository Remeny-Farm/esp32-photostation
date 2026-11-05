"""Cable clip: holds the 1.13 mm u.FL coax along the roof; fixed with a nylon screw or glue."""

import mesh

PRINT_ROT = (180, 0, 0)   # groove side up: an open groove, no bridging, no supports
COUNT = 3

CHANNEL_D = 2.0           # for the 1.13 mm coax
CHANNEL_X = -3.5          # channel centre; the screw hole sits on the other side
HOLE_X = 2.0


def build(p):
    w, l, t = p.clip
    block = mesh.box_span("cable_clip", (-w / 2, w / 2), (-l / 2, l / 2), (0, t))
    # Half-round groove in the bottom face, along the length (Y).
    channel = mesh.cyl("channel", CHANNEL_D, l + 2, (CHANNEL_X, 0, 0), axis="Y")
    hole = mesh.cyl("hole", p.wood_screw_d, t + 2, (HOLE_X, 0, t / 2))
    return mesh.cut(block, channel, hole)


def checks(p, ob):
    errs = []

    def up(x, y=0.0):
        d = mesh.ray_hits(ob, (x, y, -10), (0, 0, 1))
        return None if d is None else d - 10  # height above the bottom face

    r = CHANNEL_D / 2
    d = up(CHANNEL_X)
    if d is None or abs(d - r) > 0.05:
        errs.append(f"channel depth {d}, expected {r}")
    inside = up(CHANNEL_X + r - 0.05)
    if inside is None or inside < 0.1:
        errs.append("channel narrower than 2")
    outside = up(CHANNEL_X + r + 0.1)
    if outside is None or abs(outside) > 0.01:
        errs.append("channel wider than 2")
    for s in (-1, 1):
        if up(CHANNEL_X, s * (p.clip[1] / 2 - 0.5)) is None:
            errs.append("channel does not run the full length")
    if up(HOLE_X) is not None:
        errs.append("screw hole missing")
    return errs
