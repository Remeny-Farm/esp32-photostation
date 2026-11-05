"""Wall rail: the +X rail in the world frame. Both rails are this one print: the assembly
turns it end for end (180 deg about Y) for the -X rail, so every feature is symmetric about
the rail's mid-height, and the ticks sit on both sides of the slot.

The back face (+Y) sits on the outer face of the front wall. A hex-head channel in the back
face holds the M5 bolt head flats; a slot through the front skin lets the bolt shank and the
carriage tongue slide. Printed front face down, so the channel is an open pocket on top.
"""

import mesh

PRINT_ROT = (90.0, 0.0, 0.0)   # -Y -> -Z: front face on the bed, long axis flat
COUNT = 2

HEAD_RUN = 5.0        # channel runs this far past each slot end so the hex head can slide
CSK_D = 8.5           # 90 degree countersink diameter on the front face
TICK_W = 0.8          # engraved tick width (along Z)
TICK_DEPTH = 0.6
TICK_SHORT = 4.0
TICK_LONG = 8.0
TICK_MAJOR = 50.0     # a long tick every this many mm
TICK_MARGIN = 0.6     # between the slot edge and the tick start


def _frame(p):
    """Derived numbers shared by build() and checks()."""
    y_back = -p.t_wood
    y_front = -p.t_wood - p.rail_d
    return {
        "y_back": y_back,
        "y_front": y_front,
        "y_floor": y_back - p.channel_d,                  # channel floor = slot back end
        "z0": p.slot_z0 - p.rail_foot,
        "z1": p.slot_z1 + p.rail_foot,
        "feet": ((p.slot_z0 - p.rail_foot + p.slot_z0) / 2,
                 (p.slot_z1 + p.slot_z1 + p.rail_foot) / 2),
        "tick_dx": p.slot_w / 2 + TICK_MARGIN,           # slot centre line to the tick start
        "ticks": _ticks(p),
    }


def _ticks(p):
    """(z, major) from the slot middle outwards, so the rail reads the same turned end for
    end. The long tick in the middle is the mid rail state's bolt height."""
    mid = (p.slot_z0 + p.slot_z1) / 2
    n = int((p.slot_z1 - p.slot_z0) / 2 / p.tick_pitch)
    zs = sorted({(mid + s * k * p.tick_pitch, k) for k in range(n + 1) for s in (-1, 1)})
    return [(z, (k * p.tick_pitch) % TICK_MAJOR == 0) for z, k in zs]


def build(p):
    f = _frame(p)
    rx = p.rail_x
    yb, yf, yc = f["y_back"], f["y_front"], f["y_floor"]

    rail = mesh.box_span("rail", (rx - p.rail_w / 2, rx + p.rail_w / 2), (yf, yb), (f["z0"], f["z1"]))

    # Hex-head channel in the wall-side face (overshoots the face by 1 mm for a clean cut).
    mesh.cut(rail, mesh.box_span("channel", (rx - p.channel_w / 2, rx + p.channel_w / 2),
                                 (yc, yb + 1), (p.slot_z0 - HEAD_RUN, p.slot_z1 + HEAD_RUN)))

    # Slot through the front skin, rounded ends, overlapping the channel floor by 1 mm.
    r = p.slot_w / 2
    sy0, sy1 = yf - 1, yc + 1
    cutters = [mesh.box_span("slot", (rx - r, rx + r), (sy0, sy1), (p.slot_z0 + r, p.slot_z1 - r))]
    for zc in (p.slot_z0 + r, p.slot_z1 - r):
        cutters.append(mesh.cyl("slot_end", p.slot_w, sy1 - sy0, (rx, (sy0 + sy1) / 2, zc), "Y"))
    mesh.cut(rail, *cutters)

    # One countersunk wood-screw hole per foot. The cone passes 8.5 mm at the front face at
    # 90 degrees and meets the 4.5 mm shank hole 2 mm deeper; it overshoots 1 mm outside.
    csk_depth = (CSK_D - p.wood_screw_d) / 2
    for zc in f["feet"]:
        mesh.cut(rail,
                 mesh.cyl("foot_hole", p.wood_screw_d, p.rail_d + 2, (rx, (yf + yb) / 2, zc), "Y"),
                 mesh.cone("foot_csk", CSK_D + 2, p.wood_screw_d, csk_depth + 1,
                           (rx, yf + csk_depth / 2 - 0.5, zc), "Y"))

    # Engraved ticks on both sides of the slot, symmetric about the mid-height.
    ticks = []
    for z, major in f["ticks"]:
        ln = TICK_LONG if major else TICK_SHORT
        for s in (-1, 1):
            x0 = rx + s * f["tick_dx"]
            ticks.append(mesh.box_span("tick", (x0, x0 + s * ln),
                                       (yf - 1, yf + TICK_DEPTH), (z - TICK_W / 2, z + TICK_W / 2)))
    mesh.cut(rail, mesh.union(ticks[0], *ticks[1:]))
    return rail


def _near(errs, what, got, want, tol):
    if got is None or abs(got - want) > tol:
        errs.append(f"{what}: {got if got is None else round(got, 3)} (want {want:.3f} +-{tol})")


def _width(ob, x, y, z):
    """Gap width along X around (x, y, z), cast both ways."""
    a = mesh.ray_hits(ob, (x, y, z), (1, 0, 0))
    b = mesh.ray_hits(ob, (x, y, z), (-1, 0, 0))
    return None if a is None or b is None else a + b


def checks(p, ob):
    errs = []
    f = _frame(p)
    rx = p.rail_x
    mid = (p.slot_z0 + p.slot_z1) / 2
    yb, yf, yc = f["y_back"], f["y_front"], f["y_floor"]

    _near(errs, "slot width at mid-length", _width(ob, rx, (yf + yc) / 2, mid), p.slot_w, 0.05)
    _near(errs, "channel width at mid-length", _width(ob, rx, (yc + yb) / 2, mid), p.channel_w, 0.05)

    lo, hi = mesh.bbox(ob)
    length = hi.z - lo.z
    if length > p.bed:
        errs.append(f"rail length {length:.1f} exceeds {p.bed}")
    _near(errs, "rail length", length, (p.slot_z1 - p.slot_z0) + 2 * p.rail_foot, 0.01)
    _near(errs, "rail depth", hi.y - lo.y, p.rail_d, 0.01)
    _near(errs, "rail width", hi.x - lo.x, p.rail_w, 0.01)

    # Channel floor depth and run (the hex head must slide the whole slot).
    d = mesh.ray_hits(ob, (rx + 3.5, yb + 5, mid), (0, -1, 0))
    _near(errs, "channel depth", d, 5 + p.channel_d, 0.05)
    _near(errs, "channel run past slot_z1",
          mesh.ray_hits(ob, (rx + 3.5, (yc + yb) / 2, mid), (0, 0, 1)),
          p.slot_z1 + HEAD_RUN - mid, 0.05)
    _near(errs, "channel run past slot_z0",
          mesh.ray_hits(ob, (rx + 3.5, (yc + yb) / 2, mid), (0, 0, -1)),
          mid - (p.slot_z0 - HEAD_RUN), 0.05)

    # Foot holes: a ray down the screw axis misses; one beside it hits; the countersink is 90 deg.
    for zc in f["feet"]:
        if mesh.ray_hits(ob, (rx, 0, zc), (0, -1, 0), 100) is not None:
            errs.append(f"foot hole at z={zc:.1f} is not open")
        if mesh.ray_hits(ob, (rx + 6, 0, zc), (0, -1, 0), 100) is None:
            errs.append(f"foot at z={zc:.1f} has no material beside the hole")
        # 3.5 mm off axis the cone surface is (4.25 - 3.5) = 0.75 mm behind the front face.
        got = mesh.ray_hits(ob, (rx + 3.5, yf - 10, zc), (0, 1, 0))
        _near(errs, f"countersink at z={zc:.1f}", got, 10 + (CSK_D / 2 - 3.5), 0.1)

    # Ticks on both sides: recessed at a tick, flush between ticks, long ticks every 50 mm
    # from the middle, and the set is symmetric about the mid-height.
    zs = [z for z, _ in f["ticks"]]
    if any(abs((z0 + z1) / 2 - mid) > 1e-6 for z0, z1 in zip(zs, reversed(zs))):
        errs.append(f"ticks are not symmetric about the mid-height {mid:g}: {zs}")
    if (mid, True) not in f["ticks"]:
        errs.append(f"no long tick at the mid-height {mid:g}")
    for z, major in f["ticks"]:
        for s in (-1, 1):
            side = "+X" if s > 0 else "-X"
            x_in = rx + s * (f["tick_dx"] + 2.0)
            got = mesh.ray_hits(ob, (x_in, yf - 10, z), (0, 1, 0))
            _near(errs, f"{side} tick depth at z={z:.1f}", got, 10 + TICK_DEPTH, 0.05)
            x_end = rx + s * (f["tick_dx"] + TICK_LONG - 0.5)
            got = mesh.ray_hits(ob, (x_end, yf - 10, z), (0, 1, 0))
            _near(errs, f"{side} {'long' if major else 'short'} tick end at z={z:.1f}", got,
                  10 + (TICK_DEPTH if major else 0.0), 0.05)
            got = mesh.ray_hits(ob, (x_in, yf - 10, z + p.tick_pitch / 2), (0, 1, 0))
            _near(errs, f"{side} face between ticks at z={z + p.tick_pitch / 2:.1f}", got, 10.0, 0.05)
    return errs
