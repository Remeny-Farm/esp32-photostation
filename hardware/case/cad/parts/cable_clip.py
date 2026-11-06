"""Cable clip: holds the 1.13 mm u.FL coax along the roof; fixed with a nylon screw or glue."""

import math

import mesh

PRINT_ROT = (180, 0, 0)   # groove side up: an open groove, no bridging, no supports
COUNT = 3

CHANNEL_X = -3.5          # channel centre; the screw hole sits on the other side
HOLE_X = 2.0


def channel(p):
    """Groove width and depth. The clip face sits flush on the roof, so the whole coax must fit
    inside the groove: its diameter plus p.clr on each side and above."""
    return p.coax_d + 2 * p.clr, p.coax_d + p.clr


def build(p):
    w, l, t = p.clip
    cw, cd = channel(p)
    block = mesh.box_span("cable_clip", (-w / 2, w / 2), (-l / 2, l / 2), (0, t))
    # Rectangular groove in the bottom face, along the length (Y).
    groove = mesh.box_span("channel", (CHANNEL_X - cw / 2, CHANNEL_X + cw / 2),
                           (-l / 2 - 1, l / 2 + 1), (-1, cd))
    hole = mesh.cyl("hole", p.wood_screw_d, t + 2, (HOLE_X, 0, t / 2))
    return mesh.cut(block, groove, hole)


def checks(p, ob):
    errs = []
    cw, cd = channel(p)

    def up(x, y=0.0):
        d = mesh.ray_hits(ob, (x, y, -10), (0, 0, 1))
        return None if d is None else d - 10  # height above the bottom face

    d = up(CHANNEL_X)
    if d is None or abs(d - cd) > 0.05:
        errs.append(f"channel depth {d}, expected {cd:.2f}")
    for s in (-1, 1):
        inside = up(CHANNEL_X + s * (cw / 2 - 0.05))
        if inside is None or abs(inside - cd) > 0.05:
            errs.append(f"channel narrower than {cw:.2f} ({inside})")
        outside = up(CHANNEL_X + s * (cw / 2 + 0.1))
        if outside is None or abs(outside) > 0.01:
            errs.append(f"channel wider than {cw:.2f} ({outside})")
        if up(CHANNEL_X, s * (p.clip[1] / 2 - 0.5)) is None:
            errs.append("channel does not run the full length")

    # The coax lies on the roof (the clip's bottom face, z 0) inside the groove: from its axis,
    # every direction into the clip has at least p.clr of free space beyond the jacket.
    r = p.coax_d / 2
    for y in (-p.clip[1] / 2 + 0.5, 0.0, p.clip[1] / 2 - 0.5):
        for k in range(7):
            a = math.radians(30 * k)
            got = mesh.ray_hits(ob, (CHANNEL_X, y, r), (math.cos(a), 0, math.sin(a)))
            if got is not None and got < r + p.clr - 0.01:
                errs.append(f"coax D{p.coax_d:g} flush on the roof meets the clip at y={y:g}, "
                            f"{30 * k} deg: {got:.2f} mm from its axis")

    if up(HOLE_X) is not None:
        errs.append("screw hole missing")
    return errs
