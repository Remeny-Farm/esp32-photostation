"""Fit, interference, field-of-view and clearance checks: blender.sh verify.py

Run build.py first (check 1 reads stl/). Prints PASS <name> or FAIL <name>: detail per
check and exits 1 if any check fails. All volumes are Manifold boolean intersections; parts
that touch face to face (rail on the wall, carriage on the rails) give zero volume.
"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import assembly  # noqa: E402
import coupon  # noqa: E402
import mesh  # noqa: E402
from params import (P, RAIL_PIVOT_Z, TILTS, aim_tilt, head_center, head_in_fov,  # noqa: E402
                    lens_pose, nearest_tilt, usb_plug_box, vfov_deg)
from parts import PARTS, load  # noqa: E402

STL = HERE.parent / "stl"
MAX_MM3 = 1.0
RESULTS = []


def report(name, errs):
    RESULTS.append(not errs)
    if errs:
        for e in errs:
            print(f"FAIL {name}: {e}")
    else:
        print(f"PASS {name}")


# --- helpers -----------------------------------------------------------------------------

def _world_bbox(ob):
    m = ob.matrix_world
    pts = [m @ Vector(c) for c in ob.bound_box]
    return (Vector([min(q[i] for q in pts) for i in range(3)]),
            Vector([max(q[i] for q in pts) for i in range(3)]))


def _boxes_meet(a, b, pad=0.01):
    la, ha = _world_bbox(a)
    lb, hb = _world_bbox(b)
    return all(la[i] <= hb[i] + pad and lb[i] <= ha[i] + pad for i in range(3))


def overlap(a, b):
    """Intersection volume of a and b in world space; both stay untouched."""
    if not _boxes_meet(a, b):
        return 0.0
    ca = mesh.copy(a, "_ov_a")
    cb = mesh.copy(b, "_ov_b")
    bpy.context.view_layer.update()
    mesh.intersect(ca, cb)
    v = abs(mesh.volume(ca))
    bpy.data.objects.remove(ca, do_unlink=True)
    return v


def group_overlap(ga, gb):
    """Summed volume over member pairs, and the worst pair."""
    total, worst = 0.0, (0.0, "")
    for a in ga:
        for b in gb:
            v = overlap(a, b)
            total += v
            if v > worst[0]:
                worst = (v, f"{a.name}/{b.name}")
    return total, worst


def _point_box_dist(pt, lo, hi):
    return math.sqrt(sum(max(lo[i] - pt[i], 0.0, pt[i] - hi[i]) ** 2 for i in range(3)))


def _max_world_y(ob):
    m = ob.matrix_world
    return max((m @ v.co).y for v in ob.data.vertices)


# --- checks ------------------------------------------------------------------------------

def check_stls(p):
    names = list(PARTS) + list(coupon.NAMES)
    if not STL.is_dir():
        report("stl", [f"{STL} is missing: run blender.sh build.py first"])
        return
    for name in names:
        path = STL / f"{name}.stl"
        if not path.exists():
            report(f"stl {name}", [f"{path.name} is missing: run blender.sh build.py first"])
            continue
        mesh.reset_scene()
        bpy.ops.wm.stl_import(filepath=str(path))
        ob = bpy.context.selected_objects[0]
        errs = []
        nm = mesh.non_manifold_edges(ob)
        if nm:
            errs.append(f"{nm} non-manifold edges")
        lo, hi = mesh.bbox(ob)
        size = hi - lo
        if abs(lo.z) > 1e-3:
            errs.append(f"min z {lo.z:.3f}, not 0")
        if max(size) > p.bed:
            errs.append(f"{size.x:.1f} x {size.y:.1f} x {size.z:.1f} exceeds the {p.bed:g} cube")
        if mesh.volume(ob) <= 0:
            errs.append("no volume")
        report(f"stl {name}", errs)


def check_interference(p, objs):
    module = [objs[n] for n in ("module_body", "module_lid", "window_frame")]
    groups = {
        "module": module,
        "carriage": [objs["carriage"]],
        "rails": [objs["rail_L"], objs["rail_R"]],
        "wood": [o for n, o in objs.items() if n.startswith("wood_")],
    }
    keys = list(groups)
    errs = []
    for state in RAIL_PIVOT_Z:
        for tilt in TILTS:
            assembly.place(objs, p, state, tilt)
            for i, a in enumerate(keys):
                for b in keys[i + 1:]:
                    v, (wv, pair) = group_overlap(groups[a], groups[b])
                    if v >= MAX_MM3:
                        errs.append(f"{state} tilt {tilt}: {a}/{b} {v:.2f} mm3 (worst {pair} "
                                    f"{wv:.2f})")
    report("interference (3 rail states x 4 tilts)", errs)


def check_placeholders(p, objs):
    assembly.place(objs, p, "mid", 0)
    solids = [objs[n] for n in assembly.MODULE_PARTS]
    errs = []
    for name in assembly.MODULE_PH:
        for s in solids:
            v = overlap(objs[name], s)
            if v >= MAX_MM3:
                errs.append(f"{name} meets {s.name}: {v:.2f} mm3")
    report("placeholders inside the module", errs)


def check_usb_path(p, objs):
    """The USB-C plug goes in from below: its overmould (usb_plug_box) swept straight up from
    under the module to the receptacle must meet no module part. check_placeholders cannot
    see this, because the plugged-in overmould ends above the bottom wall and only the cable
    passes the hole; a hole that drifts off the receptacle axis shows here."""
    assembly.place(objs, p, "mid", 0)
    (x0, x1), (y0, y1), (_, z1) = usb_plug_box(p)
    path = mesh.box_span("usb_plug_path", (x0, x1), (y0, y1), (p.mod_z0 - 10.0, z1))
    path.parent = objs["module_pivot"]
    bpy.context.view_layer.update()
    errs = []
    for n in assembly.MODULE_PARTS:
        v = overlap(path, objs[n])
        if v >= MAX_MM3:
            errs.append(f"plug path meets {n}: {v:.2f} mm3")
    bpy.data.objects.remove(path, do_unlink=True)
    report("USB-C plug passes the bottom hole to the receptacle", errs)


def check_visibility(p, objs):
    obstacles = ([o for n, o in objs.items() if n.startswith("wood_")] + [objs["ph_bowl"]]
                 + [objs[n] for n in assembly.MODULE_PARTS])
    hc = Vector(head_center(p))
    r = p.head_d / 2
    targets = [hc] + [hc + Vector(d) * r for d in
                      ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    errs = []
    for state, z in RAIL_PIVOT_Z.items():
        tilt = nearest_tilt(aim_tilt(p, z))
        assembly.place(objs, p, state, tilt)
        lens, fwd = lens_pose(p, z, tilt)
        start = Vector(lens) + Vector(fwd) * 0.5
        for t in targets:
            seg = t - start
            for ob in obstacles:
                d = mesh.ray_hits(ob, start, seg.normalized(), seg.length)
                if d is not None and d < seg.length:
                    errs.append(f"{state} tilt {tilt}: ray to ({t.x:.0f}, {t.y:.0f}, {t.z:.0f}) "
                                f"hits {ob.name} at {d:.1f} mm")
        if not head_in_fov(p, z, tilt):
            errs.append(f"{state} tilt {tilt}: head not inside the frustum")
    report("head visible at every rail state", errs)


def check_bowl(p, objs):
    v = overlap(objs["ph_bowl"], objs["bowl_holder"])
    report("bowl sits in its holder", [] if v < MAX_MM3 else [f"overlap {v:.1f} mm3"])


CROP = 0.6   # central share of the image (in tangent space) that must be unobstructed
SCREW_WOOD_MIN = 5.0   # plywood between the opening (bevel included) and a rail screw hole


def _field_rays(p, state):
    """Lens start point and the ray direction for image coordinates (u, v) in -1..1."""
    z = RAIL_PIVOT_Z[state]
    tilt = nearest_tilt(aim_tilt(p, z))
    lens, fwd = lens_pose(p, z, tilt)
    fwd = Vector(fwd)
    up = Matrix.Rotation(math.radians(-tilt), 3, "X") @ Vector((0, 0, 1))
    th = math.tan(math.radians(p.hfov / 2))
    tv = math.tan(math.radians(vfov_deg(p) / 2))
    return tilt, Vector(lens) + fwd * 0.5, \
        lambda u, v: (fwd + Vector((u * th, 0, 0)) + up * (v * tv)).normalized()


def check_field(p, objs):
    """Rays over the whole frustum, no distance cap. The obstacles are the front wall, the
    carriage, both rails and the module parts; the side walls, roof and floor are the scene.
    The central crop must be clear: the grid points inside it and its boundary (where the
    corners are, which the grid only nears). The blocked share of the frame is reported."""
    obstacles = ([objs["wood_front"], objs["carriage"], objs["rail_L"], objs["rail_R"]]
                 + [objs[n] for n in assembly.MODULE_PARTS])
    n = 24
    grid = [2 * i / (n - 1) - 1 for i in range(n)]
    edge = [CROP * (2 * k / 8 - 1) for k in range(9)]
    boundary = sorted({(a, s * CROP) for a in edge for s in (-1, 1)}
                      | {(s * CROP, a) for a in edge for s in (-1, 1)})
    errs = []
    for state in RAIL_PIVOT_Z:
        tilt, start, ray = _field_rays(p, state)
        assembly.place(objs, p, state, tilt)

        def blocker(u, v):
            d = ray(u, v)
            return next((ob.name for ob in obstacles if mesh.ray_hits(ob, start, d) is not None),
                        None)
        blocked, crop_hits = 0, []
        for u in grid:
            for v in grid:
                who = blocker(u, v)
                if who:
                    blocked += 1
                    if abs(u) <= CROP and abs(v) <= CROP:
                        crop_hits.append((u, v, who))
        crop_hits += [(u, v, who) for u, v in boundary if (who := blocker(u, v))]
        print(f"info field {state} tilt {tilt}: {100 * blocked / n / n:.1f}% of the frame "
              f"blocked, {len(crop_hits)} rays blocked in the central {CROP:.0%} crop")
        if crop_hits:
            errs.append(f"{state} tilt {tilt}: {len(crop_hits)} crop rays blocked, e.g. "
                        + ", ".join(f"(u {u:+.2f}, v {v:+.2f}) by {w}" for u, v, w in crop_hits[:4]))
    report(f"central {CROP:.0%} of the image is clear at every rail state", errs)


def check_screw_wood(p, objs):
    """Plywood between each rail screw hole and the opening, measured on the wood_front mesh
    from the hole edge towards the opening at the outer face and at the inner face (where
    the bevel takes the most)."""
    front = objs["wood_front"]
    errs = []
    worst = 1e9
    for s in (-1, 1):
        x = s * (p.rail_x - p.wood_screw_d / 2)
        for z in load("rail")._frame(p)["feet"]:
            for y in (-p.t_wood + 0.01, -0.01):
                d = mesh.ray_hits(front, (x, y, z), (-s, 0, 0))
                worst = min(worst, 1e9 if d is None else d)
                if d is None or d < SCREW_WOOD_MIN:
                    errs.append(f"rail screw at x={s * p.rail_x:g} z={z:g}, y={y:g}: "
                                f"{d if d is None else round(d, 2)} mm of wood to the opening")
    report(f"rail screw holes keep >= {SCREW_WOOD_MIN:g} mm of plywood to the opening "
           f"(nearest {worst:.2f} mm)", errs)


def check_frame_removal(p, objs):
    frame = objs["window_frame"]
    others = ([objs["carriage"], objs["rail_L"], objs["rail_R"], objs["module_body"]]
              + [o for n, o in objs.items() if n.startswith("wood_")])
    errs = []
    for state in RAIL_PIVOT_Z:
        for tilt in (0, 15):
            assembly.place(objs, p, state, tilt)
            base = frame.matrix_world.copy()
            for d in range(1, 51, 2):
                frame.matrix_world = base @ Matrix.Translation((0.0, 0.0, float(d)))
                bpy.context.view_layer.update()
                for o in others:
                    v = overlap(frame, o)
                    if v >= MAX_MM3:
                        errs.append(f"{state} tilt {tilt}: frame lifted {d} mm meets {o.name} "
                                    f"({v:.2f} mm3)")
                        break
                else:
                    continue
                break
            frame.matrix_world = base
            frame.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    report("window frame slides out at tilt 0 and 15", errs)


def _fasteners(p, state, tilt):
    """World points of every metal fastener at one state."""
    rail = load("rail")
    bowl = load("bowl_holder")
    body = load("module_body")
    carr = assembly.carriage_matrix(p, state)
    mod = assembly.module_matrix(p, state, tilt)
    cx = sum(p.cheek_x) / 2
    a = math.radians(tilt)
    pts = {}
    for s in (-1, 1):
        pts[f"pivot screw {s:+d}"] = carr @ Vector((s * cx, 0.0, 0.0))
        pts[f"index screw {s:+d}"] = carr @ Vector((s * cx, -p.index_r * math.cos(a),
                                                     p.index_r * math.sin(a)))
        pts[f"rail bolt {s:+d}"] = carr @ Vector((s * p.rail_x, max(p.carr_y), p.bolt_dz))
        for z in rail._frame(p)["feet"]:
            pts[f"rail screw {s:+d} z{z:g}"] = Vector((s * p.rail_x, -p.t_wood - p.rail_d / 2, z))
    for i, (x, y) in enumerate(bowl._hole_centres(p)):
        pts[f"bowl screw {i}"] = Vector((x, y, bowl.TAB_T / 2))
    for i, (bx, bz) in enumerate(body.lid_bosses(p)):
        pts[f"lid screw {i}"] = mod @ Vector((bx, p.mod_y1, bz))
    return pts


def check_metal(p, objs):
    lo, hi = mesh.bbox(objs["ph_antenna"])
    errs = []
    worst = (1e9, "")
    for state in RAIL_PIVOT_Z:
        for tilt in TILTS:
            for name, pt in _fasteners(p, state, tilt).items():
                d = _point_box_dist(pt, lo, hi)
                worst = min(worst, (d, f"{name} ({state}, tilt {tilt})"))
                if d < p.metal_keepout:
                    errs.append(f"{name} at {state} tilt {tilt}: {d:.1f} mm from the antenna")
    report(f"metal keep-out >= {p.metal_keepout:g} mm (nearest: {worst[1]}, {worst[0]:.0f} mm)",
           errs)


def check_standoff(p, objs):
    limit = -p.t_wood - 1
    errs = []
    worst = (1e9, "")
    for state in RAIL_PIVOT_Z:
        for tilt in TILTS:
            assembly.place(objs, p, state, tilt)
            for n in ("window_frame", "module_body"):
                y = _max_world_y(objs[n])
                clear = -p.t_wood - y
                worst = min(worst, (clear, f"{n} at {state} tilt {tilt}"))
                if y > limit + 1e-6:
                    errs.append(f"{n} at {state} tilt {tilt} reaches y={y:.2f} "
                                f"(limit {limit:g}, clearance to the wall {clear:.2f} mm)")
    print(f"info standoff: minimum clearance to the wall outer face {worst[0]:.2f} mm "
          f"({worst[1]})")
    report(f"lens standoff (module at y <= {limit:g})", errs)


def info_states(p):
    half = math.tan(math.radians(p.hfov / 2))
    for state, z in RAIL_PIVOT_Z.items():
        tilt = nearest_tilt(aim_tilt(p, z))
        lens, _ = lens_pose(p, z, tilt)
        d = math.dist(lens, head_center(p))
        px = 2048 * p.head_d / (2 * d * half)
        print(f"info {state}: lens ({lens[0]:.1f}, {lens[1]:.1f}, {lens[2]:.1f}), tilt {tilt} "
              f"(aim {aim_tilt(p, z):.1f}), head {d:.0f} mm away, head {px:.0f} px of 2048 "
              f"(vfov {vfov_deg(p):.1f})")


def main():
    p = P()
    check_stls(p)
    mesh.reset_scene()
    objs = assembly.build(p)
    check_interference(p, objs)
    check_placeholders(p, objs)
    check_usb_path(p, objs)
    check_visibility(p, objs)
    check_field(p, objs)
    check_screw_wood(p, objs)
    check_bowl(p, objs)
    check_frame_removal(p, objs)
    check_metal(p, objs)
    check_standoff(p, objs)
    info_states(p)
    failed = RESULTS.count(False)
    print(f"{'FAIL' if failed else 'PASS'} verify: {len(RESULTS) - failed}/{len(RESULTS)} checks")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
