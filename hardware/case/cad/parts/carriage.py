"""Carriage: the frame that rides both rails and holds the tilting module.

Module local frame: origin at the tilt pivot, x across, y forward (towards the wall), z up.
The plate back face (+Y) rests on the rail fronts. Two plate wings (|x| cheek..carr_x) carry
the rail bolt and a guide tongue each; a bottom bar ties them together. There is no top bar:
the module ties the cheeks together through the pivot screws, and nothing swings over its top.
The cheeks carry the pivot and the tilt index holes; their ears outside the plate's y band
have a 45 degree chamfer underneath. Printed upright (Z up) on the bottom bar: no bridges,
no overhang steeper than 45 degrees.
"""

import math

import bmesh
import bpy
from mathutils import Matrix

import mesh
from params import TILTS

PRINT_ROT = (0.0, 0.0, 0.0)    # Z up, bottom bar on the bed
COUNT = 1

BAR_T = 8.0           # bottom bar thickness (z): carr_z[0] .. carr_z[0] + BAR_T
WING_ABOVE_BOLT = 34.0    # wing top above the rail bolt; the cheeks sit 24 mm deep in it
CHEEK_OVERLAP = 24.0  # cheek reaches this far down into the wing
FUZZ = 1.0            # cutters overshoot faces by this much
OVERHANG_NZ = -0.72   # face normal z below this prints as an overhang (more than 45 deg)


def _frame(p):
    """Derived numbers shared by build() and checks()."""
    wing_top = p.bolt_dz + WING_ABOVE_BOLT                           # -6
    return {
        "bar_top": p.carr_z[0] + BAR_T,                              # -76
        "wing_top": wing_top,
        "cheek_z0": wing_top - CHEEK_OVERLAP,                        # -30
        "tongue_w": p.slot_w - 2 * p.clr,                            # 4.9, 0.3 per side
    }


def _prism(name, x0, x1, poly):
    """Convex (y, z) polygon extruded along X from x0 to x1."""
    bm = bmesh.new()
    for x in (x0, x1):
        for y, z in poly:
            bm.verts.new((x, y, z))
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build(p):
    f = _frame(p)
    y_hi, y_lo = max(p.carr_y), min(p.carr_y)
    cx0, cx1 = p.cheek_x
    cy_hi, cy_lo = p.cheek_y
    z_hi = p.cheek_z[1]
    z_lo = f["cheek_z0"]

    # Bottom bar across the full width, then a wing per side up to the wing top.
    bar = mesh.box_span("carriage", (-p.carr_x, p.carr_x), p.carr_y, (p.carr_z[0], f["bar_top"]))
    parts = []
    # Cheek profile in (y, z): box with the underside of both ears cut at 45 degrees down to
    # the plate faces, so the ears print without supports.
    cheek_poly = [(cy_hi, z_hi), (cy_lo, z_hi),
                  (cy_lo, z_lo + (y_lo - cy_lo)), (y_lo, z_lo),
                  (y_hi, z_lo), (cy_hi, z_lo + (cy_hi - y_hi))]
    for sx in (-1, 1):
        parts.append(mesh.box_span("wing", sorted((sx * cx0, sx * p.carr_x)), p.carr_y,
                                   (p.carr_z[0], f["wing_top"])))
        parts.append(_prism("cheek", *sorted((sx * cx0, sx * cx1)), cheek_poly))
        # Guide tongue on the rail-facing (+Y) side. Its base spans tongue_len; the ends are
        # chamfered at 45 degrees (the tongue is tongue[1] high), so it prints without a bridge.
        h = p.tongue[1]
        tz0, tz1 = p.bolt_dz - p.tongue_len / 2, p.bolt_dz + p.tongue_len / 2
        parts.append(_prism("tongue", sx * p.rail_x - f["tongue_w"] / 2, sx * p.rail_x + f["tongue_w"] / 2,
                            [(y_hi - 0.5, tz0), (y_hi, tz0), (y_hi + h, tz0 + h),
                             (y_hi + h, tz1 - h), (y_hi, tz1), (y_hi - 0.5, tz1)]))
    mesh.union(bar, *parts)

    # Pivot: one hole along X at (y 0, z 0) through both cheeks (nothing else is on the axis).
    cuts = [mesh.cyl("pivot", p.pivot_clear_d, 2 * (cx1 + FUZZ), (0, 0, 0), "X")]
    # Index holes on the arc behind the pivot, through both cheeks.
    for t in TILTS:
        a = math.radians(t)
        cuts.append(mesh.cyl("index", p.index_clear_d, 2 * (cx1 + FUZZ),
                             (0, -p.index_r * math.cos(a), p.index_r * math.sin(a)), "X"))
    # M5 bolt holes through wing and tongue.
    depth = (y_hi + p.tongue[1]) - y_lo + 2 * FUZZ
    for sx in (-1, 1):
        cuts.append(mesh.cyl("bolt", p.bolt_d + 0.5, depth,
                             (sx * p.rail_x, (y_hi + p.tongue[1] + y_lo) / 2, p.bolt_dz), "Y"))
    mesh.cut(bar, *cuts)
    return bar


def _near(errs, what, got, want, tol):
    if got is None or abs(got - want) > tol:
        errs.append(f"{what}: {got if got is None else round(got, 3)} (want {want:.3f} +-{tol})")


def _passes(ob, origin, direction, r, perp):
    """True if a ray along `direction` through the hole centre misses and rays offset by
    (r - 0.1) miss but rays offset by (r + 0.1) hit, in both perpendicular directions."""
    ok = mesh.ray_hits(ob, origin, direction) is None
    for k, d in enumerate(perp):
        for sgn in (-1, 1):
            def at(off):
                o = list(origin)
                o[d] += sgn * off
                return mesh.ray_hits(ob, o, direction)
            ok = ok and at(r - 0.1) is None and at(r + 0.1) is not None
    return ok


def _overhang_area(p, ob):
    """Area of faces that face down steeper than 45 degrees, above the bed, outside the
    horizontal holes. Their roofs are small arches that print without support."""
    f = _frame(p)
    holes = [("x", 0.0, 0.0, p.pivot_clear_d / 2)]
    holes += [("x", -p.index_r * math.cos(math.radians(t)), p.index_r * math.sin(math.radians(t)),
               p.index_clear_d / 2) for t in TILTS]
    holes += [("y", sx * p.rail_x, p.bolt_dz, (p.bolt_d + 0.5) / 2) for sx in (-1, 1)]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bm.normal_update()
    bed = p.carr_z[0] + 0.01
    area, spots = 0.0, []
    for face in bm.faces:
        c = face.calc_center_median()
        if face.normal.z >= OVERHANG_NZ or c.z <= bed:
            continue
        if any((math.hypot(c.y - u, c.z - v) if ax == "x" else math.hypot(c.x - u, c.z - v)) <= r + 0.05
               for ax, u, v, r in holes):
            continue
        area += face.calc_area()
        spots.append((round(c.x, 1), round(c.y, 1), round(c.z, 1)))
    bm.free()
    return area, spots


def checks(p, ob):
    errs = []
    f = _frame(p)
    cx0, cx1 = p.cheek_x
    y_hi, y_lo = max(p.carr_y), min(p.carr_y)
    cy_hi, cy_lo = p.cheek_y
    z_lo = f["cheek_z0"]

    # Cheeks: inner and outer faces, rear end, top, and the 45 degree chamfers underneath.
    for sx in (-1, 1):
        _near(errs, f"cheek inner face x={sx * cx0:g}",
              mesh.ray_hits(ob, (-sx * 30, -10, 5), (sx, 0, 0)), 30 + cx0, 0.01)
        _near(errs, f"cheek outer face x={sx * cx1:g}",
              mesh.ray_hits(ob, (sx * 60, -10, 5), (-sx, 0, 0)), 60 - cx1, 0.01)
        xm = sx * (cx0 + cx1) / 2
        _near(errs, f"cheek rear end y={cy_lo:g}", mesh.ray_hits(ob, (xm, -40, 5), (0, 1, 0)), 40 + cy_lo, 0.01)
        _near(errs, f"cheek front end y={cy_hi:g}", mesh.ray_hits(ob, (xm, 40, 5), (0, -1, 0)), 40 - cy_hi, 0.01)
        _near(errs, "cheek top", mesh.ray_hits(ob, (xm, -10, 40), (0, 0, -1)), 40 - p.cheek_z[1], 0.01)
        # underside: 45 degrees from the plate face out to the ear end, measured from below
        for y in (-12.0, 5.0):
            want = z_lo + ((y_lo - y) if y < y_lo else (y - y_hi))
            _near(errs, f"cheek chamfer at y={y:g}", mesh.ray_hits(ob, (xm, y, -60), (0, 0, 1)),
                  want + 60, 0.01)

    # Pivot holes: coaxial at (+-36, 0, 0), diameter measured from inside the window; the
    # whole axis is free between the outer faces (no wing on it).
    r = p.pivot_clear_d / 2
    for sx in (-1, 1):
        if not _passes(ob, (-sx * 30, 0, 0), (-sx, 0, 0), r, (1, 2)):
            errs.append(f"pivot hole at x={sx * (cx0 + cx1) / 2:g} is not a coaxial D{p.pivot_clear_d} hole")
    if mesh.ray_hits(ob, (-100, 0, 0), (1, 0, 0)) is not None:
        errs.append("pivot axis is blocked between the two outer faces")

    # Index holes: four per cheek on the arc behind the pivot.
    r = p.index_clear_d / 2
    for sx in (-1, 1):
        for t in TILTS:
            a = math.radians(t)
            y, z = -p.index_r * math.cos(a), p.index_r * math.sin(a)
            if not _passes(ob, (-sx * 30, y, z), (-sx, 0, 0), r, (1, 2)):
                errs.append(f"index hole {t} deg on the {'+' if sx > 0 else '-'}X cheek is missing "
                            f"or not D{p.index_clear_d} at y={y:.2f} z={z:.2f}")

    # Wings stop below the pivot; bottom bar spans the full width.
    for sx in (-1, 1):
        _near(errs, f"wing top at x={sx * 50}", mesh.ray_hits(ob, (sx * 50, 0, 20), (0, 0, -1)),
              20 - f["wing_top"], 0.01)
    _near(errs, "bottom bar top", mesh.ray_hits(ob, (0, 0, 0), (0, 0, -1)), -f["bar_top"], 0.01)
    _near(errs, "bottom bar underside", mesh.ray_hits(ob, (0, 0, -100), (0, 0, 1)), 100 + p.carr_z[0], 0.01)
    if mesh.ray_hits(ob, (0, 0, 30), (0, 0, -1)) is not None and \
            mesh.ray_hits(ob, (0, 0, 30), (0, 0, -1)) < 30 - f["bar_top"] - 0.01:
        errs.append("something spans the window above the bottom bar")

    # Bolt holes through wing and tongue at (+-rail_x, *, bolt_dz); tongue size.
    r = (p.bolt_d + 0.5) / 2
    # Probe the tongue on its full-height lug between the bolt hole and the end ramp.
    tp = (r + p.tongue_len / 2 - p.tongue[1]) / 2
    for sx in (-1, 1):
        if not _passes(ob, (sx * p.rail_x, -10, p.bolt_dz), (0, 1, 0), r, (0, 2)):
            errs.append(f"bolt hole at x={sx * p.rail_x:g} z={p.bolt_dz:g} is not a through D{2 * r:g} hole")
        _near(errs, f"tongue height at x={sx * p.rail_x:g}",
              mesh.ray_hits(ob, (sx * p.rail_x + 2.0, 20, p.bolt_dz - tp), (0, -1, 0)),
              20 - y_hi - p.tongue[1], 0.01)
        w = (mesh.ray_hits(ob, (sx * p.rail_x, y_hi + 1, p.bolt_dz + tp), (1, 0, 0)),
             mesh.ray_hits(ob, (sx * p.rail_x, y_hi + 1, p.bolt_dz + tp), (-1, 0, 0)))
        _near(errs, f"tongue width at x={sx * p.rail_x:g}", None if None in w else sum(w), f["tongue_w"], 0.01)
        # 1 mm above the base the 45 degree end ramp has moved 1 mm inwards
        _near(errs, f"tongue length at x={sx * p.rail_x:g}",
              mesh.ray_hits(ob, (sx * p.rail_x + 1.5, y_hi + 1, p.bolt_dz + p.tongue_len), (0, 0, -1)),
              p.tongue_len / 2 + 1, 0.01)
    lo, hi = mesh.bbox(ob)
    _near(errs, "carriage width", hi.x - lo.x, 2 * p.carr_x, 0.01)

    # Module clearance at every tilt (rotate about X by -tilt, nose down).
    for t in TILTS:
        probe = mesh.copy(ob, "tilt_probe")
        body = mesh.box_span("tilt_body", (-p.mod_x, p.mod_x), (p.mod_y1, p.mod_y0), (p.mod_z0, p.mod_z1))
        body.data.transform(Matrix.Rotation(-math.radians(t), 4, "X"))
        body.data.update()
        mesh.intersect(probe, body)
        v = abs(mesh.volume(probe))
        bpy.data.objects.remove(probe, do_unlink=True)
        if v >= 1.0:
            errs.append(f"module body at tilt {t} deg intersects the carriage by {v:.1f} mm3")

    # Printability in the Z-up print orientation.
    area, spots = _overhang_area(p, ob)
    if area > 1.0:
        errs.append(f"{area:.1f} mm2 of downward-facing faces above the bed, e.g. at {spots[:4]}")
    return errs
