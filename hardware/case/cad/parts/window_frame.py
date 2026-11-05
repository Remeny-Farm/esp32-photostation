"""Removable window frame of the camera module (module local frame, see params.py).

It slides down into the two guides on the body front. An acrylic pane sits in a pocket that
opens to the back (towards the lens); the 0.5 mm lip in front retains it. Beside the pane the
frame is solid: lighting is external, so the frame carries no light windows.
"""

import math

import mesh
from mathutils import Matrix

# Front face (+y) on the bed: the lip in front of the pane is the first layers and the pane
# pocket opens upward.
PRINT_ROT = (-90.0, 0.0, 0.0)
COUNT = 1

OVER = 1.0  # cutter overshoot beyond the part, so no cut face is coplanar with a part face


def _dims(p):
    y0 = p.mod_y0
    y1 = y0 + p.frame_d
    z1 = p.frame_top_z
    zc = p.lens[2]                       # the pane is centred on the lens
    half = p.pane[0] / 2 + p.press       # pocket half-size: pane plus a press fit per side
    # The pocket is deep enough for the pane plus the shroud that stands proud under it.
    pocket_y1 = y0 + p.pane[1] + p.shroud_h
    return y0, y1, z1, zc, half, pocket_y1


def build(p):
    y0, y1, z1, zc, half, pocket_y1 = _dims(p)
    w = p.frame_w / 2
    ap = p.pane[0] / 2 - 1.0             # aperture: 1 mm of pane edge is held by the lip

    ob = mesh.box_span("window_frame", (-w, w), (y0, y1), (z1 - p.frame_h, z1))

    gx, gy, gz = p.grip
    # The tab grows from the frame front (y1) at z1 to its own front face (y0 + gy) at
    # z1 + (y1 - y0 - gy): a 45 degree chamfer on the bed-facing side, so it needs no support.
    tab = mesh.box_span("tab", (-gx / 2, gx / 2), (y0, y1), (z1 - 1.0, z1 + gz))
    n = math.sqrt(0.5)
    d = (y1 + z1) * n + 5.0              # cutter centre, along (y, z) = (1, 1)/sqrt 2
    ch = mesh.box("chamfer", (gx * 2, 10.0, 10.0))
    ch.data.transform(Matrix.Translation((0, d * n, d * n)) @ Matrix.Rotation(math.radians(45), 4, "X"))
    # Remove only what lies in front of the tab's own front face.
    mesh.intersect(ch, mesh.box_span("ahead", (-gx, gx), (y0 + gy, y1 + 5.0), (-50.0, 50.0)))
    mesh.cut(tab, ch)
    mesh.union(ob, tab)

    mesh.cut(ob, mesh.box_span("pocket", (-half, half), (y0 - OVER, pocket_y1),
                               (zc - half, zc + half)))
    mesh.cut(ob, mesh.box_span("aperture", (-ap, ap), (pocket_y1 - OVER, y1 + OVER),
                               (zc - ap, zc + ap)))

    # Channel for the lens shroud, so the frame can slide up past it: from the pocket's
    # bottom edge to the frame's bottom edge, open at the bottom.
    cw = p.shroud_od / 2 + p.clr
    mesh.cut(ob, mesh.box_span("shroud_channel", (-cw, cw), (y0 - OVER, y0 + p.shroud_h + p.clr),
                               (z1 - p.frame_h - OVER, zc - half + 1.0)))
    return ob


def _d(ob, origin, direction):
    return mesh.ray_hits(ob, origin, direction)


def checks(p, ob):
    errs = []
    y0, y1, z1, zc, half, pocket_y1 = _dims(p)
    tol = 0.02

    def expect(name, got, want, t=tol):
        if got is None or abs(got - want) > t:
            errs.append(f"{name}: {got if got is None else round(got, 3)}, want {want}")

    # Pane pocket: width and height across, measured inside it at mid depth.
    mid = (y0 + pocket_y1) / 2
    # Off-centre in x for the z size: the shroud channel opens the pocket centre to the bottom.
    for axis, d, ox in (("x", (1, 0, 0), 0.0), ("z", (0, 0, 1), 7.0)):
        a = _d(ob, (ox, mid, zc), d)
        b = _d(ob, (ox, mid, zc), tuple(-c for c in d))
        expect(f"pane pocket {axis} size", None if a is None or b is None else a + b, 2 * half)
    # Depth behind the lip is pane thickness + shroud; the lip itself is 0.5 thick.
    back = _d(ob, (half - 0.5, y0 - 5, zc), (0, 1, 0))
    expect("pocket depth behind the lip", None if back is None else back - 5,
           p.pane[1] + p.shroud_h)
    front = _d(ob, (half - 0.5, y1 + 5, zc), (0, -1, 0))
    expect("front lip thickness", None if front is None or back is None else
           (y1 + 5 - front) - (y0 - 5 + back), 0.5)

    # Front aperture is open: rays just inside its edges meet nothing, just outside they hit.
    ap = p.pane[0] / 2 - 1.0
    for axis, o in (("x", (ap - 0.1, y0 - 5, zc)), ("z", (0, y0 - 5, zc + ap - 0.1)),
                    ("centre", (0, y0 - 5, zc))):
        if _d(ob, o, (0, 1, 0)) is not None:
            errs.append(f"front aperture not open ({axis}, width {2 * ap})")
    for axis, o in (("x", (ap + 0.1, y0 - 5, zc)), ("z", (0, y0 - 5, zc + ap + 0.1))):
        if _d(ob, o, (0, 1, 0)) is None:
            errs.append(f"front aperture wider than {2 * ap} in {axis}")

    # Solid beside the pane: full frame thickness where the old light windows were.
    for s in (-1, 1):
        x = s * 18.0
        back = _d(ob, (x, y0 - 5, zc), (0, 1, 0))
        front = _d(ob, (x, y1 + 5, zc), (0, -1, 0))
        expect(f"solid frame at x={x:g}",
               None if back is None or front is None else (y1 + 5 - front) - (y0 - 5 + back),
               p.frame_d)
        expect(f"frame back face at x={x:g}", back, 5.0)

    # Shroud channel: floor at shroud_h + clr, open at the bottom, joined to the pocket.
    floor = _d(ob, (0, y0 - 5, -34.0), (0, 1, 0))
    expect("shroud channel floor", None if floor is None else floor - 5 + y0, y0 + 1.8, 0.05)
    if _d(ob, (0, y0 + 0.5, z1 - p.frame_h - 10), (0, 0, 1)) is None:
        errs.append("shroud channel does not open into the pane pocket")
    else:
        up = _d(ob, (0, y0 + 0.5, z1 - p.frame_h - 10), (0, 0, 1))
        expect("shroud channel run to the pocket top", z1 - p.frame_h - 10 + up, zc + half)

    # Grip tab: 45 degree chamfer on the bed-facing side, flat front at y0 + grip y.
    top = _d(ob, (0, y1 + 5, z1 + 1.0), (0, -1, 0))   # on the chamfer: y + z = y1 + z1
    expect("grip tab chamfer at z+1", None if top is None else y1 + 5 - top, y1 - 1.0)
    top = _d(ob, (0, y1 + 5, z1 + p.grip[2] - 0.1), (0, -1, 0))
    expect("grip tab front face at top", None if top is None else y1 + 5 - top, y0 + p.grip[1])

    # Outer size and thickness, measured on the plain edge strip away from every cut.
    ex = -p.frame_w / 2 + 2.0
    lo, hi = mesh.bbox(ob)
    expect("outer width", hi.x - lo.x, p.frame_w, 1e-3)
    expect("overall height with grip tab", hi.z - lo.z, p.frame_h + p.grip[2], 1e-3)
    dn = _d(ob, (ex, mid, z1 + 10), (0, 0, -1))
    up = _d(ob, (ex, mid, z1 - p.frame_h - 10), (0, 0, 1))
    expect("frame height", None if dn is None or up is None else
           (z1 + 10 - dn) - (z1 - p.frame_h - 10 + up), p.frame_h)
    t1 = _d(ob, (ex, y0 - 5, -10), (0, 1, 0))
    t2 = _d(ob, (ex, y1 + 5, -10), (0, -1, 0))
    expect("frame thickness", None if t1 is None or t2 is None else
           (y1 + 5 - t2) - (y0 - 5 + t1), p.frame_d)
    return errs
