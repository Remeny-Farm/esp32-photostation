"""Fit coupons: short slices of the sliding fits, printed before the full parts.

Each coupon is one object with two pieces side by side (GAP apart), already in a
support-free print orientation (each piece keeps its parent part's print orientation):
  coupon_rail    40 mm of the rail's slotted middle + 40 mm of the carriage wing with its
                 guide tongue and bolt hole (tongue in slot, bolt through both).
  coupon_window  the module body front strip (guides, lip, stop, shroud, lens bore) + the
                 lower 20 mm of the window frame (slides down into the guides to the stop).
  coupon_sled    a module body side-wall section with the sled groove and stop + the
                 matching edge strip of the board sled.
"""

import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mesh  # noqa: E402
from parts import load  # noqa: E402
from parts import module_body as body  # noqa: E402

GAP = 5.0
SLICE = 40.0
FRAME_SLICE = 20.0
STRIP_DEPTH = 10.0   # body front strip, y from mod_y0 - STRIP_DEPTH + 5.5 to the lip front
NAMES = ("coupon_rail", "coupon_window", "coupon_sled")
PRINT_ROT = (0.0, 0.0, 0.0)   # coupons are built in print orientation


def _slice(part, p, xs, ys, zs, rot):
    """part ∩ box, turned into the part's print orientation and dropped onto the bed."""
    ob = load(part).build(p)
    mesh.intersect(ob, mesh.box_span(f"{part}_slice_box", xs, ys, zs))
    mesh.apply_print_rotation(ob, rot)
    return ob


def _side_by_side(name, a, b):
    """Join b to the +X side of a with GAP between them; one object, two shells."""
    lo_a, hi_a = mesh.bbox(a)
    lo_b, hi_b = mesh.bbox(b)
    dx = hi_a.x + GAP - lo_b.x
    dy = (lo_a.y + hi_a.y) / 2 - (lo_b.y + hi_b.y) / 2
    bm = bmesh.new()
    bm.from_mesh(a.data)
    tmp = bmesh.new()
    tmp.from_mesh(b.data)
    bmesh.ops.translate(tmp, vec=(dx, dy, 0.0), verts=tmp.verts)
    me_b = bpy.data.meshes.new("tmp_b")
    tmp.to_mesh(me_b)
    tmp.free()
    bm.from_mesh(me_b)
    bpy.data.meshes.remove(me_b)
    bpy.data.objects.remove(a, do_unlink=True)
    bpy.data.objects.remove(b, do_unlink=True)
    ob = mesh._obj(name, bm)
    mesh.apply_print_rotation(ob, PRINT_ROT)
    return ob


def coupon_rail(p):
    rail = load("rail")
    rx, hw = p.rail_x, p.rail_w / 2
    mid = (p.slot_z0 + p.slot_z1) / 2
    a = _slice("rail", p, (rx - hw - 1, rx + hw + 1), (-p.t_wood + 1, -p.t_wood - p.rail_d - 1),
               (mid - SLICE / 2, mid + SLICE / 2), rail.PRINT_ROT)
    # Carriage wing over the same rail width, centred on the bolt; same -Y-face-down
    # orientation as the rail slice, so the tongue stands up.
    b = _slice("carriage", p, (rx - hw, rx + hw), (-10.0, 10.0),
               (p.bolt_dz - SLICE / 2, p.bolt_dz + SLICE / 2), (90.0, 0.0, 0.0))
    return _side_by_side("coupon_rail", a, b)


def coupon_window(p):
    wf = load("window_frame")
    y_lo = 10.5 - STRIP_DEPTH
    a = _slice("module_body", p, (-p.mod_x - 1, p.mod_x + 1), (y_lo, 12.0),
               (p.frame_top_z - p.frame_h - 6.0, p.mod_z1 + 1), body.PRINT_ROT)
    z0 = p.frame_top_z - p.frame_h
    b = _slice("window_frame", p, (-p.frame_w, p.frame_w), (-50.0, 50.0),
               (z0 - 1, z0 + FRAME_SLICE), wf.PRINT_ROT)
    return _side_by_side("coupon_window", a, b)


def coupon_sled(p):
    sled = load("board_sled")
    ix = body.inner_x(p)
    st, sb = p.sled_z
    # Below the pivot and index bosses (z >= -5), behind the stop pad, the whole groove.
    a = _slice("module_body", p, (ix - body.RIB - 4.0, p.mod_x + 1),
               (p.mod_y1 - 1, body.STOP_Y + 2.0), (sb - 6.0, st + 2.0), body.PRINT_ROT)
    hw = sled.half_width(p)
    b = _slice("board_sled", p, (hw - 8.0, hw + 1), (-50.0, 50.0), (sb - 1, st + 1),
               sled.PRINT_ROT)
    return _side_by_side("coupon_sled", a, b)


def build(p):
    return {"coupon_rail": coupon_rail(p), "coupon_window": coupon_window(p),
            "coupon_sled": coupon_sled(p)}


def checks(p, ob):
    """Print-orientation errors for a coupon (the body's overhang rule)."""
    errs = []
    nm = mesh.non_manifold_edges(ob)
    if nm:
        errs.append(f"{nm} non-manifold edges")
    errs += body.overhang_errors(ob, (0.0, 0.0, 0.0))
    return errs
