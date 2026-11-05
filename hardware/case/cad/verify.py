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
                    lens_pose, nearest_tilt, vfov_deg)
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
    check_visibility(p, objs)
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
