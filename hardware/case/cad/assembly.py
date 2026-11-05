"""The assembled test bed: plywood corridor, rails, carriage, module, holders, placeholders.

build(p, state, tilt) places every part at one rail state and tilt. The module parts hang
under two empties, so the live scene can be re-posed by hand: `carriage_origin` moves along
the rail (world = local + (0, pivot_y, pivot_z), no rotation), and its child `module_pivot`
rotates about X by -tilt (nose down), exactly as params.local_to_world does. place() moves
the two empties for another state; verify.py uses it.

The plywood boards are not printed: cut_list() and cut_notes() are the wood drawing.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import components  # noqa: E402
import mesh  # noqa: E402
from params import RAIL_PIVOT_Z, aim_tilt, lens_pose, nearest_tilt, vfov_deg, _rot  # noqa: E402
from parts import load  # noqa: E402

ROOF_HOLE_D = 6.0
FRUSTUM_LEN = 300.0
CLIP_COUNT = 3

# Viewport colours (RGBA). The frustum alpha only shows in material/solid-with-alpha views.
COLOURS = {
    "wood": (0.76, 0.60, 0.42, 1.0),
    "petg": (0.85, 0.85, 0.85, 1.0),
    "board": (0.10, 0.55, 0.20, 1.0),
    "camera": (0.03, 0.03, 0.03, 1.0),
    "usb": (0.20, 0.20, 0.20, 1.0),
    "bowl": (0.15, 0.35, 0.85, 1.0),
    "head": (1.00, 0.50, 0.05, 1.0),
    "antenna": (0.85, 0.65, 0.13, 1.0),
    "led": (0.95, 0.95, 0.80, 1.0),
    "frustum": (1.00, 0.90, 0.10, 0.25),
}
PH_MATERIAL = {"ph_xiao": "board", "ph_perfboard": "board", "ph_camera": "camera",
               "ph_usb": "usb", "ph_bowl": "bowl", "ph_head": "head", "ph_antenna": "antenna",
               "ph_led_l": "led", "ph_led_r": "led"}

MODULE_PARTS = ("module_body", "module_lid", "board_sled", "window_frame")
MODULE_PH = ("ph_xiao", "ph_camera", "ph_usb", "ph_perfboard", "ph_led_l", "ph_led_r")


# --- wood --------------------------------------------------------------------------------

def _boards(p):
    """(name, x span, y span, z span) of each plywood board in the world frame."""
    t, hw, h, ln = p.t_wood, p.inner_w / 2, p.inner_h, p.inner_len
    return [
        ("wood_floor", (-hw - t, hw + t), (-t, ln), (-t, 0.0)),
        ("wood_roof", (-hw - t, hw + t), (-t, ln), (h, h + t)),
        ("wood_side_l", (-hw - t, -hw), (-t, ln), (0.0, h)),
        ("wood_side_r", (hw, hw + t), (-t, ln), (0.0, h)),
        ("wood_front", (-hw, hw), (-t, 0.0), (0.0, h)),
    ]


def wood(p):
    """Plywood boards: floor and roof span the full width, the side walls stand on the
    floor, the front wall sits between them. The entrance end (Y inner_len) is open."""
    obs = []
    for name, xs, ys, zs in _boards(p):
        ob = mesh.box_span(name, xs, ys, zs)
        if name == "wood_front":
            mesh.cut(ob, mesh.box_span("opening", (-p.open_w / 2, p.open_w / 2),
                                       (-p.t_wood - 1, 1.0), (p.open_z0, p.open_z1)))
        if name == "wood_roof":
            mesh.cut(ob, mesh.cyl("roof_hole", ROOF_HOLE_D, p.t_wood + 2,
                                  (0.0, p.roof_hole_y, p.inner_h + p.t_wood / 2), segments=32))
        obs.append(ob)
    return obs


def cut_list(p):
    """(name, qty, length, width, thickness) per board; length is the longer side."""
    rows = {}
    for name, xs, ys, zs in _boards(p):
        dims = sorted((xs[1] - xs[0], ys[1] - ys[0], zs[1] - zs[0]), reverse=True)
        key = "wood_side" if name.startswith("wood_side") else name
        n, _ = rows.get(key, (0, None))
        rows[key] = (n + 1, dims)
    return [(k, n, d[0], d[1], d[2]) for k, (n, d) in rows.items()]


def cut_notes(p):
    """Opening and drill positions, measured on each board from the named edges."""
    rail = load("rail")
    bowl = load("bowl_holder")
    hw, t = p.inner_w / 2, p.t_wood
    feet = rail._frame(p)["feet"]
    notes = [
        f"wood_front: opening {p.open_w:g} x {p.open_z1 - p.open_z0:g}, centred across, "
        f"from {p.open_z0:g} to {p.open_z1:g} above the bottom edge",
        "wood_front: rail screws, 4 x pilot for 4.5 mm wood screws at "
        + ", ".join(f"({hw + sx * p.rail_x:g}, {z:g})" for sx in (-1, 1) for z in feet)
        + " (from the left edge, from the bottom edge; outer face)",
        f"wood_roof: u.FL hole D{ROOF_HOLE_D:g} at ({hw + t:g}, {p.roof_hole_y + t:g}) "
        "(from the left edge, from the front edge)",
        f"wood_roof: antenna holder, 2 x D4.5 for M4 nylon bolts at "
        f"({hw + t - 18:g}, {p.antenna_y + t:g}) and ({hw + t + 18:g}, {p.antenna_y + t:g}) "
        "(from the left edge, from the front edge); nylon only, no metal within "
        f"{p.metal_keepout:g} mm of the radiator",
        "wood_floor: bowl holder, 3 x pilot for 4.5 mm wood screws at "
        + ", ".join(f"({x + hw + t:.1f}, {y + t:.1f})" for x, y in bowl._hole_centres(p))
        + " (from the left edge, from the front edge)",
    ]
    return notes


# --- scene helpers -----------------------------------------------------------------------

def _collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _move_to(col_name, obs):
    col = _collection(col_name)
    for ob in obs:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        col.objects.link(ob)
    return obs


def _material(key):
    name = f"mat_{key}"
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = COLOURS[key]
        try:
            mat.use_nodes = True
        except (AttributeError, TypeError):
            pass
        tree = getattr(mat, "node_tree", None)
        if tree is not None:
            bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is not None:
                bsdf.inputs["Base Color"].default_value = COLOURS[key]
                if COLOURS[key][3] < 1.0:
                    bsdf.inputs["Alpha"].default_value = COLOURS[key][3]
    return mat


def _paint(ob, key):
    ob.data.materials.clear()
    ob.data.materials.append(_material(key))


def _empty(name, parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = 20.0
    bpy.context.scene.collection.objects.link(e)
    e.parent = parent
    return e


def _frustum(p, state, tilt):
    """Pyramid from the lens: 85 deg across, vfov up and down, FRUSTUM_LEN long."""
    lens, fwd = lens_pose(p, RAIL_PIVOT_Z[state], tilt)
    up = Vector(_rot((0.0, 0.0, 1.0), tilt))
    fwd, right = Vector(fwd), Vector((1.0, 0.0, 0.0))
    a = FRUSTUM_LEN * math.tan(math.radians(p.hfov / 2))
    b = FRUSTUM_LEN * math.tan(math.radians(vfov_deg(p) / 2))
    apex = Vector(lens)
    base = apex + fwd * FRUSTUM_LEN
    bm = bmesh.new()
    v0 = bm.verts.new(apex)
    corners = [bm.verts.new(base + right * sx * a + up * sz * b)
               for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        bm.faces.new((v0, corners[i], corners[(i + 1) % 4]))
    bm.faces.new(list(reversed(corners)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh._obj(f"frustum_{state}", bm)
    ob.display_type = "WIRE"
    ob["tilt"] = tilt
    _paint(ob, "frustum")
    return ob


# --- placement ---------------------------------------------------------------------------

def carriage_matrix(p, state):
    return Matrix.Translation((0.0, p.pivot_y, RAIL_PIVOT_Z[state]))


def module_matrix(p, state, tilt):
    """Module local -> world: rotate about X by -tilt, then translate (params.local_to_world)."""
    return carriage_matrix(p, state) @ Matrix.Rotation(-math.radians(tilt), 4, "X")


def place(objs, p, state, tilt):
    """Re-pose the rig for another rail state and tilt."""
    objs["carriage_origin"].matrix_world = carriage_matrix(p, state)
    objs["module_pivot"].matrix_basis = Matrix.Rotation(-math.radians(tilt), 4, "X")
    objs["carriage_origin"]["state"] = state
    objs["module_pivot"]["tilt"] = tilt
    bpy.context.view_layer.update()


def _clip_positions(p):
    """Three clips under the roof between the roof hole and the antenna holder, channel on
    the coax line (x = 0). For show only: the clips have no fixed place."""
    clip = load("cable_clip")
    y0 = p.roof_hole_y
    y1 = p.antenna_y - p.ant_plate[1] / 2
    return [(-clip.CHANNEL_X, y0 + (y1 - y0) * k / (CLIP_COUNT + 1), p.inner_h)
            for k in range(1, CLIP_COUNT + 1)]


def build(p, state="mid", tilt=None):
    """Every part at rail state `state` and `tilt` (default: nearest_tilt(aim_tilt))."""
    if tilt is None:
        tilt = nearest_tilt(aim_tilt(p, RAIL_PIVOT_Z[state]))
    objs = {}

    for ob in _move_to("wood", wood(p)):
        _paint(ob, "wood")
        objs[ob.name] = ob

    carr_origin = _empty("carriage_origin")
    pivot = _empty("module_pivot", carr_origin)
    objs["carriage_origin"], objs["module_pivot"] = carr_origin, pivot

    printed = []
    rail_r = load("rail").build(p)
    rail_r.name = "rail_R"
    rail_l = mesh.mirror_x(rail_r, "rail_L")
    printed += [rail_r, rail_l]

    carriage = load("carriage").build(p)
    carriage.name = "carriage"
    carriage.parent = carr_origin
    printed.append(carriage)

    for name in MODULE_PARTS:
        ob = load(name).build(p)
        ob.name = name
        ob.parent = pivot
        printed.append(ob)

    for name in ("bowl_holder", "antenna_holder"):
        ob = load(name).build(p)
        ob.name = name
        printed.append(ob)

    flip = Matrix.Rotation(math.pi, 4, "X")   # channel side up against the roof
    for i, pos in enumerate(_clip_positions(p)):
        ob = load("cable_clip").build(p)
        ob.name = f"cable_clip_{i + 1}"
        ob.data.transform(flip)
        ob.matrix_world = Matrix.Translation(pos)
        printed.append(ob)

    for ob in _move_to("printed", printed):
        _paint(ob, "petg")
        objs[ob.name] = ob

    for ob in components.build_module_parts(p):
        ob.parent = pivot
        objs[ob.name] = ob
    for ob in components.build_world_parts(p):
        objs[ob.name] = ob
    for name, ob in objs.items():
        if name.startswith("ph_"):
            _paint(ob, PH_MATERIAL.get(name, "board"))

    frusta = [_frustum(p, s, nearest_tilt(aim_tilt(p, z))) for s, z in RAIL_PIVOT_Z.items()]
    for ob in _move_to("frustum", frusta):
        objs[ob.name] = ob

    _move_to("printed", [carr_origin, pivot])
    place(objs, p, state, tilt)
    return objs
