"""Bowl holder: a ring with three screw tabs that fixes the bowl's place on the floor."""

import math

import mesh

PRINT_ROT = (0, 0, 0)
COUNT = 1

TAB_T = 5.0          # tab thickness (z)
TAB_R = 9.0          # tab pad radius
TAB_OFFSET = 6.0     # hole centre beyond the ring outer radius; the pad bites 3 mm into the wall
TAB_ANGLES = (90.0, 210.0, 330.0)   # 120 degrees apart, none on the X axis
SINK_D = 9.0         # countersink diameter at the top of the tab


def bore_d(p, z):
    """Bore diameter at height z: the bowl is a cone, so the bore follows it with p.clr."""
    return p.bowl_d_base + (p.bowl_d_top - p.bowl_d_base) * z / p.bowl_h + 2 * p.clr


def _hole_centres(p):
    r = bore_d(p, p.ring_h) / 2 + p.ring_wall + TAB_OFFSET
    return [(r * math.cos(math.radians(a)), p.bowl_y + r * math.sin(math.radians(a)))
            for a in TAB_ANGLES]


def build(p):
    ring = mesh.cyl("bowl_holder", bore_d(p, p.ring_h) + 2 * p.ring_wall, p.ring_h,
                    (0, p.bowl_y, p.ring_h / 2))
    # Tapered bore, extended 1 mm past both faces along the same cone.
    ring_hole = mesh.cone("ring_hole", bore_d(p, -1), bore_d(p, p.ring_h + 1), p.ring_h + 2,
                          (0, p.bowl_y, p.ring_h / 2))
    pads = [mesh.cyl(f"pad{i}", 2 * TAB_R, TAB_T, (x, y, TAB_T / 2))
            for i, (x, y) in enumerate(_hole_centres(p))]
    mesh.union(ring, *pads)
    mesh.cut(ring, ring_hole)
    # Countersunk 45 degree holes: shank through, cone opens at the top face.
    sink_h = (SINK_D - p.wood_screw_d) / 2
    for i, (x, y) in enumerate(_hole_centres(p)):
        shank = mesh.cyl(f"shank{i}", p.wood_screw_d, TAB_T + 2, (x, y, TAB_T / 2))
        sink = mesh.cone(f"sink{i}", p.wood_screw_d, SINK_D + 2 * 0.5, sink_h + 0.5,
                         (x, y, TAB_T - sink_h + (sink_h + 0.5) / 2))
        mesh.cut(ring, shank, sink)
    return ring


def checks(p, ob):
    errs = []
    lo, hi = mesh.bbox(ob)
    if max(hi.x - lo.x, hi.y - lo.y) > p.bed:
        errs.append("bowl holder exceeds the bed: split it")
    mid = p.ring_h / 2
    right = mesh.ray_hits(ob, (0, p.bowl_y, mid), (1, 0, 0))
    left = mesh.ray_hits(ob, (0, p.bowl_y, mid), (-1, 0, 0))
    want = bore_d(p, mid)
    if right is None or left is None or abs(right + left - want) > 0.1:
        got = None if right is None or left is None else right + left
        errs.append(f"inner diameter {got}, expected {want}")
    for i, (x, y) in enumerate(_hole_centres(p)):
        if mesh.ray_hits(ob, (x, y, TAB_T + 20), (0, 0, -1)) is not None:
            errs.append(f"tab hole {i} missing")
        # A ray just inside the shank wall must miss, just outside it must hit.
        r = p.wood_screw_d / 2
        if mesh.ray_hits(ob, (x + r - 0.1, y, 0.5 - 10), (0, 0, 1)) is not None:
            errs.append(f"tab hole {i} narrower than {p.wood_screw_d}")
        if mesh.ray_hits(ob, (x + r + 0.1, y, 0.5 - 10), (0, 0, 1)) is None:
            errs.append(f"tab hole {i} wider than {p.wood_screw_d}")
    return errs
