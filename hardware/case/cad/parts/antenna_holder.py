"""Antenna holder: a plate under the roof with a pocket for the self-adhesive FPC radiator."""

import mesh

PRINT_ROT = (180, 0, 0)   # pocket side up, so the pocket prints open
COUNT = 1

POCKET = (18.0, 38.0)     # x, y: the 17.5 x 37.4 radiator plus clearance, long side along Y
GROOVE_W = 1.6
GROOVE_D = 1.2
SLOT_X = 18.0             # slot centres, for M4 nylon bolts (no metal near the radiator)


def build(p):
    w, l, t = p.ant_plate
    z0 = p.inner_h - t
    cx, cy = 0.0, p.antenna_y
    plate = mesh.box_span("antenna_holder", (cx - w / 2, cx + w / 2), (cy - l / 2, cy + l / 2),
                          (z0, p.inner_h))
    d = p.ant_pocket_depth
    pocket = mesh.box_span("pocket", (cx - POCKET[0] / 2, cx + POCKET[0] / 2),
                           (cy - POCKET[1] / 2, cy + POCKET[1] / 2), (z0 - 1, z0 + d))
    # Coax leaves the pocket towards -Y (the module side) and runs to the plate edge.
    groove = mesh.box_span("groove", (cx - GROOVE_W / 2, cx + GROOVE_W / 2),
                           (cy - l / 2 - 1, cy - POCKET[1] / 2 + 1), (z0 - 1, z0 + GROOVE_D))
    sw, sl = p.ant_slot
    slots = [mesh.box_span(f"slot{i}", (sx - sw / 2, sx + sw / 2), (cy - sl / 2, cy + sl / 2),
                           (z0 - 1, p.inner_h + 1)) for i, sx in enumerate((-SLOT_X, SLOT_X))]
    return mesh.cut(plate, pocket, groove, *slots)


def checks(p, ob):
    errs = []
    z0 = p.inner_h - p.ant_plate[2]
    cx, cy = 0.0, p.antenna_y

    def up(x, y):
        return mesh.ray_hits(ob, (x, y, z0 - 10), (0, 0, 1))

    def height(x, y):
        """Height of the first surface above the plate underside; None = a through hole."""
        d = up(x, y)
        return None if d is None else d - 10

    def near(v, want, tol=0.05):
        return v is not None and abs(v - want) <= tol

    d = p.ant_pocket_depth
    if not near(height(cx, cy), d):
        errs.append(f"pocket depth {height(cx, cy)}, expected {d}")
    for s in (-1, 1):
        if not near(height(cx + s * (POCKET[0] / 2 - 0.1), cy + 5), d):
            errs.append(f"pocket narrower than {POCKET[0]} in x")
        if not near(height(cx + s * (POCKET[0] / 2 + 0.1), cy + 5), 0.0):
            errs.append(f"pocket wider than {POCKET[0]} in x")
        if not near(height(cx + 4, cy + s * (POCKET[1] / 2 - 0.1)), d):
            errs.append(f"pocket shorter than {POCKET[1]} in y")
        if not near(height(cx + 4, cy + s * (POCKET[1] / 2 + 0.1)), 0.0):
            errs.append(f"pocket longer than {POCKET[1]} in y")
    y_edge = cy - p.ant_plate[1] / 2
    if not near(height(cx, y_edge + 1), GROOVE_D):
        errs.append("coax groove missing at the module-side edge")
    if not near(height(cx + GROOVE_W / 2 + 0.1, y_edge + 1), 0.0):
        errs.append(f"coax groove wider than {GROOVE_W}")
    sw, sl = p.ant_slot
    for sx in (-SLOT_X, SLOT_X):
        if height(sx, cy) is not None:
            errs.append(f"slot at x={sx} missing")
            continue
        for s in (-1, 1):
            if height(sx + s * (sw / 2 - 0.1), cy) is not None:
                errs.append(f"slot at x={sx} narrower than {sw}")
            if height(sx + s * (sw / 2 + 0.1), cy) is None:
                errs.append(f"slot at x={sx} wider than {sw}")
            if height(sx, cy + s * (sl / 2 - 0.1)) is not None:
                errs.append(f"slot at x={sx} shorter than {sl}")
            if height(sx, cy + s * (sl / 2 + 0.1)) is None:
                errs.append(f"slot at x={sx} longer than {sl}")
    return errs
