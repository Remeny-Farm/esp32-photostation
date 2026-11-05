"""Camera module body (module local frame, see params.py).

A five-sided PETG box, open at the rear (closed by module_lid). The front carries the lens
bore and shroud, the two LED pockets and the guides of the window frame; the side walls carry
the pivot and index bosses and the grooves the board sled slides in; the bottom has the USB-C
hole, vents and the zip-tie anchor; the top has the u.FL slot.

Print orientation: top face on the bed. Front-face-down (the plan's first choice) cannot work:
the frame guides stand 5.5 mm proud of the front face, so the whole front wall would hang in
the air. Top down, the guides and the frame channel are vertical, and the cavity is shaped so
nothing needs support: the bottom (now the last layers) is a 14 mm bridge between two 45 deg
chamfers, the top corners carry 45 deg fills that also hold the lid screw pilots, and every
feature that points down in print (guide tops, frame stop, shroud, LED pad tops, rib tops) is
cut at 45 deg or stays a ledge of 1.3 mm or less.
"""

import math

import bmesh
import bpy
from mathutils import Euler

import mesh

PRINT_ROT = (180.0, 0.0, 0.0)
COUNT = 1

RIB = 1.0          # groove depth: the sled ribs stand this far off the side walls
ZIP_H = 3.0        # zip-tie anchor bar height under the body bottom
STOP_Y = -10.8     # front end of the sled grooves: the sled stops here
OVERHANG_COS = 0.74  # a print-down face steeper than ~48 deg from vertical is an overhang
BRIDGE_MAX = 15.0


def inner_x(p):
    """Side wall inner face, which is also the sled groove floor."""
    return p.mod_x - p.wall


def usb_center_y(p):
    return p.board_back_y + 1.25 + 2.1


def lid_bosses(p):
    """(x, z) of the two lid screw pilots: top-left and bottom-right corner."""
    return [(-(p.mod_x - 4.0), p.mod_z1 - 4.0), (p.mod_x - 4.0, p.mod_z0 + 4.0)]


def prism(name, pts, axis, a0, a1):
    """Extrude a convex 2D polygon along axis from a0 to a1.
    pts are (u, v): axis Y -> (x, z), X -> (y, z), Z -> (x, y)."""
    def v3(u, v, a):
        return {"Y": (u, a, v), "X": (a, u, v), "Z": (u, v, a)}[axis]
    bm = bmesh.new()
    lo = [bm.verts.new(v3(u, v, a0)) for u, v in pts]
    hi = [bm.verts.new(v3(u, v, a1)) for u, v in pts]
    bm.faces.new(lo)
    bm.faces.new(hi)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    return mesh._obj(name, bm)


def overhang_errors(ob, rot, limit=BRIDGE_MAX):
    """Group the faces that point down in the print orientation (and are not on the bed)
    into connected regions; a region narrower than `limit` in both directions is a short
    bridge or ledge, anything wider needs support and is an error."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bm.transform(Euler([math.radians(a) for a in rot]).to_matrix().to_4x4())
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    zmin = min(v.co.z for v in bm.verts)
    down = {f.index for f in bm.faces
            if f.normal.z < -OVERHANG_COS and f.calc_center_median().z > zmin + 0.05
            and f.calc_area() > 1e-6}
    parent = {i: i for i in down}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in bm.edges:
        fs = [f.index for f in e.link_faces if f.index in down]
        for a, b in zip(fs, fs[1:]):
            parent[find(a)] = find(b)
    regions = {}
    for i in down:
        regions.setdefault(find(i), []).append(i)
    errs = []
    for faces in regions.values():
        pts = [v.co for i in faces for v in bm.faces[i].verts]
        dx = max(p.x for p in pts) - min(p.x for p in pts)
        dy = max(p.y for p in pts) - min(p.y for p in pts)
        if min(dx, dy) > limit:
            z = sum(p.z for p in pts) / len(pts)
            errs.append(f"unsupported overhang {dx:.1f} x {dy:.1f} mm at print z {z - zmin:.1f}")
    bm.free()
    return errs


TOP_FILL_DROP = 3.0   # the top corner fills start this far above the sled top
FLOOR_HALF = 7.0      # half-width of the flat bottom bridge (USB overmould is 12.4 wide)
RIB_H = 2.0           # rib height beside the groove
RIB_Y0_GAP = 1.8      # ribs stop short of the rear face: the lid rim (1.5) plus clearance
LED_PAD = 1.3         # backing pad behind each LED pocket: pocket (2.5) is deeper than the wall
WIRE_D = 3.0
ZIP_W, ZIP_LEG, ZIP_TUNNEL = 4.0, 1.5, (4.0, 2.0)  # bar width (x), leg length (y), tunnel y x z
VENT = (20.0, 2.0)    # bottom vent slot x, y
VENT_PITCH = 3.5
LID_PILOT_DEPTH = 8.0
E = 0.1               # overlap so that unions and cuts never share a face


def cavity(p):
    """Inner cross-section (x, z), constant from the rear face to the front wall: the box
    inside the walls with 45 deg chamfers in the top and bottom corners."""
    ix = inner_x(p)
    top, bot = p.mod_z1 - p.wall, p.mod_z0 + p.wall
    zt = p.sled_z[0] + TOP_FILL_DROP          # top fill starts here on the wall
    xt = ix - (top - zt)
    zb = bot + (ix - FLOOR_HALF)
    return [(-FLOOR_HALF, bot), (FLOOR_HALF, bot), (ix, zb), (ix, zt), (xt, top), (-xt, top),
            (-ix, zt), (-ix, zb)]


def inset(pts, d):
    """Offset a convex counter-clockwise polygon inwards by d."""
    n = len(pts)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L   # inward normal for CCW
        lines.append(((x0 + nx * d, y0 + ny * d), (x1 - x0, y1 - y0)))
    out = []
    for i in range(n):
        (p0, d0), (p1, d1) = lines[i - 1], lines[i]
        den = d0[0] * d1[1] - d0[1] * d1[0]
        t = ((p1[0] - p0[0]) * d1[1] - (p1[1] - p0[1]) * d1[0]) / den
        out.append((p0[0] + d0[0] * t, p0[1] + d0[1] * t))
    return out


def teardrop(r, cx, cz, segments=64):
    """Circle with a 45 deg roof towards +z (print-down for this part)."""
    pts = [(cx, cz + r * math.sqrt(2))]
    for i in range(segments + 1):
        t = math.radians(135 + 270 * i / segments)
        pts.append((cx + r * math.cos(t), cz + r * math.sin(t)))
    return pts


def _sides(p):
    """Per side wall: sled ribs and stop pad, pivot and index boss."""
    ix = inner_x(p)
    st, sb = p.sled_z
    zl, zh = sb - p.clr - RIB_H, st + p.clr + RIB_H
    parts = []
    for s in (-1, 1):
        # Pad over the whole groove height; the groove is cut out behind STOP_Y below.
        prof = [(s * (ix + E), zl), (s * (ix - RIB), zl), (s * (ix - RIB), zh),
                (s * (ix + E), zh + RIB + E)]
        parts.append(prism("ribs", prof, "Y", p.mod_y1 + RIB_Y0_GAP, p.mod_y0 - p.wall + E))
        parts.append(mesh.cyl("pivot_boss", 10.0, 8.0 + E, (s * (ix - 4 + E / 2), 0, 0), "X"))
        parts.append(mesh.cyl("index_boss", 8.0, 6.0 + E, (s * (ix - 3 + E / 2), -p.index_r, 0),
                              "X"))
    return parts


def _front(p):
    """Front face: LED backing pads (inside), guides, frame stop and shroud (outside)."""
    y0, yi = p.mod_y0, p.mod_y0 - p.wall
    lx, _, lz = p.lens
    lw, ld, lh = p.led_pocket
    parts = []
    for s in (-1, 1):
        x0, x1 = s * p.led_x - lw / 2 - 1.2, s * p.led_x + lw / 2 + 1.2
        zb, zt = lz - lh / 2 - 1.2, lz + lh / 2 + 1.2
        yb = y0 - ld - 1.2
        pad = prism("led_pad", [(yi + E, zb), (yb, zb), (yb, zt - (yi - yb)), (yi + E, zt)],
                    "X", min(x0, x1), max(x0, x1))
        parts.append(pad)

    gy1, lip_y0 = 10.5, 9.3
    gz0, gz1 = -38.3, p.frame_top_z
    guides = None
    for s in (-1, 1):
        g = mesh.box_span("guide", (s * 28.3, s * 31.3), (y0 - E, gy1), (gz0, gz1))
        mesh.union(g, mesh.box_span("lip", (s * 26.5, s * 31.3), (lip_y0, gy1), (gz0, gz1)))
        guides = g if guides is None else mesh.union(guides, g)
    # 45 deg tops: at the face the guides still end at frame_top_z, the lip ends lower.
    mesh.cut(guides, prism("guide_top", [(y0 - E / 2, gz1 + E / 2), (gy1 + 1, gz1 - (gy1 + 1 - y0)),
                                         (gy1 + 1, gz1 + 10), (y0 - E / 2, gz1 + 10)],
                           "X", -p.mod_x - 1, p.mod_x + 1))
    parts.append(guides)
    # Frame stop: a 1 mm flat seat, then 45 deg under it (it points down in print).
    parts.append(prism("stop", [(y0 - E, gz0), (y0 + 1.0, gz0), (lip_y0, gz0 - (lip_y0 - y0 - 1.0)),
                                (y0 - E, gz0 - (lip_y0 - y0 - 1.0))], "X", -31.3, 31.3))
    parts.append(prism("shroud", teardrop(p.shroud_od / 2, lx, lz), "Y", y0 - E, y0 + p.shroud_h))
    return parts


def _zip_bar(p):
    yb = usb_center_y(p) - p.usb_hole[1] / 2 - 1.0      # 1 mm behind the USB hole
    ty, tz = ZIP_TUNNEL
    ylen = ty + 2 * ZIP_LEG
    bar = mesh.box_span("zip_bar", (-ZIP_W / 2, ZIP_W / 2), (yb - ylen, yb),
                        (p.mod_z0 - ZIP_H, p.mod_z0 + E))
    mesh.cut(bar, mesh.box_span("zip_tunnel", (-ZIP_W, ZIP_W), (yb - ZIP_LEG - ty, yb - ZIP_LEG),
                                (p.mod_z0 - tz, p.mod_z0)))
    return bar, yb - ylen


def _cuts(p, vent_y0):
    ix = inner_x(p)
    y0, yi = p.mod_y0, p.mod_y0 - p.wall
    lx, _, lz = p.lens
    lw, ld, lh = p.led_pocket
    c = []
    # Sled grooves behind the stop.
    for s in (-1, 1):
        c.append(mesh.box_span("groove", (s * (ix - RIB - E), s * ix), (p.mod_y1 - 1, STOP_Y),
                               (p.sled_z[1] - p.clr, p.sled_z[0] + p.clr)))
        c.append(mesh.cyl("pivot_pilot", p.pivot_pilot_d, 8.0 + p.wall + 2,
                          (s * (p.mod_x - (8.0 + p.wall) / 2), 0, 0), "X", 32))
        c.append(mesh.cyl("index_pilot", p.index_pilot_d, 6.0 + p.wall + 2,
                          (s * (p.mod_x - (6.0 + p.wall) / 2), -p.index_r, 0), "X", 32))
        c.append(mesh.box_span("led_pocket", (s * p.led_x - lw / 2, s * p.led_x + lw / 2),
                               (y0 - ld, y0 + 1), (lz - lh / 2, lz + lh / 2)))
        c.append(mesh.cyl("led_wire", WIRE_D, 3.0, (s * p.led_x, y0 - ld - 0.6,
                                                    lz + lh / 2 - WIRE_D), "Y", 32))
    # Lens bore through wall and shroud, 45 deg entry chamfer on the inner face.
    c.append(mesh.cyl("bore", p.lens_bore_d, 10.0, (lx, y0, lz), "Y"))
    ch = 1.0
    c.append(mesh.cone("bore_chamfer", p.lens_bore_d + 2 * (ch + E), p.lens_bore_d, ch + E,
                       (lx, yi + (ch - E) / 2, lz), "Y"))
    # Bottom: USB-C hole and vents.
    uy = usb_center_y(p)
    hx, hy = p.usb_hole
    c.append(mesh.box_span("usb_hole", (-hx / 2, hx / 2), (uy - hy / 2, uy + hy / 2),
                           (p.mod_z0 - 1, p.mod_z0 + p.wall + 1)))
    vx, vy = VENT
    for i in range(3):
        y = vent_y0 - 1.5 - i * VENT_PITCH
        c.append(mesh.box_span("vent", (-vx / 2, vx / 2), (y - vy, y),
                               (p.mod_z0 - 1, p.mod_z0 + p.wall + 10)))
    # Top: u.FL slot, open to the rear.
    w = p.ufl_slot_w
    c.append(mesh.box_span("ufl_slot", (-w / 2, w / 2), (p.mod_y1 - 1, p.board_back_y + 2),
                           (p.mod_z1 - p.wall - 1, p.mod_z1 + 1)))
    # Lid screw pilots.
    for bx, bz in lid_bosses(p):
        c.append(mesh.cyl("lid_pilot", p.lid_screw_pilot_d, LID_PILOT_DEPTH + 1,
                          (bx, p.mod_y1 + (LID_PILOT_DEPTH - 1) / 2, bz), "Y", 32))
    return c


def build(p):
    ob = mesh.box_span("module_body", (-p.mod_x, p.mod_x), (p.mod_y1, p.mod_y0),
                       (p.mod_z0, p.mod_z1))
    mesh.cut(ob, prism("cavity", cavity(p), "Y", p.mod_y1 - 1, p.mod_y0 - p.wall))
    bar, bar_y1 = _zip_bar(p)
    mesh.union(ob, *_sides(p), *_front(p), bar)
    mesh.cut(ob, *_cuts(p, bar_y1))
    return ob


def checks(p, ob):
    bpy.context.view_layer.update()
    errs = []

    def ray(o, d):
        return mesh.ray_hits(ob, o, d)

    def near(name, got, want, tol=0.05):
        if got is None or abs(got - want) > tol:
            errs.append(f"{name}: {None if got is None else round(got, 3)}, want {want:g}")

    def radial(name, c, axes, want):
        for d in axes:
            near(f"{name} radius {d}", ray(c, d), want)

    X = ((1, 0, 0), (-1, 0, 0))
    Y = ((0, 1, 0), (0, -1, 0))
    Z = ((0, 0, 1), (0, 0, -1))
    lx, ly, lz = p.lens
    ix = inner_x(p)

    # Lens bore through the front wall and shroud, with the inner entry chamfer.
    radial("lens bore", (lx, ly, lz), X + Z, p.lens_bore_d / 2)
    if ray((lx, 30, lz), (0, -1, 0)) is not None:
        errs.append("lens bore is not open on axis")
    got = ray((lx, p.mod_y0 - p.wall + 0.2, lz), (1, 0, 0))
    if got is None or got < p.lens_bore_d / 2 + 0.5:
        errs.append(f"no inner entry chamfer on the lens bore ({got})")

    # Pivot and index pilots on both sides, and the bosses they sit in.
    for s in (-1, 1):
        radial(f"pivot pilot x={s * 31:g}", (s * 31, 0, 0), Y + Z, p.pivot_pilot_d / 2)
        near(f"pivot boss end x={s:+d}", ray((0, 0, -3), (s, 0, 0)), ix - 8)
        radial(f"index pilot x={s * 31:g}", (s * 31, -p.index_r, 0), Y + Z, p.index_pilot_d / 2)
        near(f"index boss end x={s:+d}", ray((0, -p.index_r, -3), (s, 0, 0)), ix - 6)

    # USB-C hole in the bottom.
    zb = p.mod_z0 + p.wall / 2
    uy = usb_center_y(p)
    radial("USB hole x", (0, uy, zb), X, p.usb_hole[0] / 2)
    radial("USB hole y", (0, uy, zb), Y, p.usb_hole[1] / 2)
    yz = uy - p.usb_hole[1] / 2 - 1.0 - ZIP_LEG - ZIP_TUNNEL[0] / 2
    if ray((-10, yz, p.mod_z0 - ZIP_TUNNEL[1] / 2), (1, 0, 0)) is not None:
        errs.append("zip-tie tunnel under the bottom is not open along x")
    for i in range(3):
        y = yz - ZIP_TUNNEL[0] / 2 - ZIP_LEG - 1.5 - VENT[1] / 2 - i * VENT_PITCH
        got = ray((5, y, p.mod_z0 - 5), (0, 0, 1))
        if got is None or got < p.wall + 10:
            errs.append(f"bottom vent at y={y:g} is not open")

    # LED pockets: 2.5 deep, 9 wide, with a wire hole into the interior.
    for s in (-1, 1):
        near(f"LED pocket depth x={s * p.led_x:g}", ray((s * p.led_x, 20, p.lens[2]), (0, -1, 0)),
             20 - p.mod_y0 + p.led_pocket[1])
        radial(f"LED pocket x={s * p.led_x:g}", (s * p.led_x, p.mod_y0 - 1, p.lens[2]), X,
               p.led_pocket[0] / 2)
        if ray((s * p.led_x, 20, p.lens[2] + p.led_pocket[2] / 2 - WIRE_D), (0, -1, 0)) is not None:
            errs.append(f"LED wire hole at x={s * p.led_x:g} does not reach the interior")

    # u.FL slot in the top, open to the rear edge.
    zt = p.mod_z1 - p.wall / 2
    radial("u.FL slot", (0, -20, zt), X, p.ufl_slot_w / 2)
    if ray((0, -20, zt), (0, -1, 0)) is not None:
        errs.append("u.FL slot is not open to the rear")
    near("u.FL slot front end", ray((0, -20, zt), (0, 1, 0)), (p.board_back_y + 2) + 20)

    # Sled grooves: floor at the wall inner face over y -13.2 .. -10.8, stop in front.
    zg = (p.sled_z[0] + p.sled_z[1]) / 2
    for s in (-1, 1):
        for y in (p.sled_rib_y[1] + 0.1, (p.sled_rib_y[0] + p.sled_rib_y[1]) / 2,
                  p.sled_rib_y[0] - 0.1, -30.0):
            near(f"sled groove floor x={s:+d} y={y:g}", ray((s * 25, y, zg), (s, 0, 0)), ix - 25)
        near(f"sled stop x={s:+d}", ray((s * 25, STOP_Y + 0.3, zg), (s, 0, 0)), ix - RIB - 25)
        for z in (p.sled_z[0] + 1.3, p.sled_z[1] - 1.3):
            near(f"sled rib x={s:+d} z={z:g}", ray((s * 25, -20, z), (s, 0, 0)), ix - RIB - 25)

    # Lid screw pilots, 8 deep from the rear face.
    for bx, bz in lid_bosses(p):
        radial(f"lid pilot ({bx:g}, {bz:g})", (bx, p.mod_y1 + 4, bz), X + Z,
               p.lid_screw_pilot_d / 2)
        near(f"lid pilot depth ({bx:g}, {bz:g})", ray((bx, p.mod_y1 - 5, bz), (0, 1, 0)), 5 + 8)

    # Envelope: the box, plus the guides in front and the zip-tie bar below.
    lo, hi = mesh.bbox(ob)
    for name, got, lim, sign in (("min x", lo.x, -p.mod_x, -1), ("max x", hi.x, p.mod_x, 1),
                                 ("min y", lo.y, p.mod_y1, -1), ("max y", hi.y, 10.5, 1),
                                 ("min z", lo.z, p.mod_z0 - ZIP_H, -1),
                                 ("max z", hi.z, p.mod_z1, 1)):
        if (got - lim) * sign > 1e-3:
            errs.append(f"envelope {name} {got:.2f} beyond {lim:g}")

    errs += overhang_errors(ob, PRINT_ROT)
    return errs
