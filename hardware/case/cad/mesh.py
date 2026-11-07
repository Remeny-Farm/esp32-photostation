"""Small bpy helpers: primitives, Manifold booleans, measuring, STL export."""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.001
    s.unit_settings.length_unit = "MILLIMETERS"


def _obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, size, center=(0, 0, 0)):
    """Axis-aligned box; size (x, y, z), centred on center."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def box_span(name, x, y, z):
    """Box from (lo, hi) spans per axis, in any order."""
    lo = [min(a) for a in (x, y, z)]
    hi = [max(a) for a in (x, y, z)]
    return box(name, [h - l for l, h in zip(lo, hi)], [(h + l) / 2 for l, h in zip(lo, hi)])


# create_cone runs along +Z; these map +Z onto the named axis.
_AXIS = {"X": Euler((0, math.pi / 2, 0)), "Y": Euler((-math.pi / 2, 0, 0)), "Z": Euler((0, 0, 0))}


def cone(name, d1, d2, h, center=(0, 0, 0), axis="Z", segments=64):
    """Frustum along axis, d1 at the low end, d2 at the high end (low/high along +axis)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments,
                          radius1=d1 / 2, radius2=d2 / 2, depth=h)
    bmesh.ops.transform(bm, matrix=_AXIS[axis].to_matrix().to_4x4(), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def cyl(name, d, h, center=(0, 0, 0), axis="Z", segments=64):
    return cone(name, d, d, h, center, axis, segments)


def _boolean(target, other, op):
    m = target.modifiers.new("b", "BOOLEAN")
    m.operation = op
    m.object = other
    m.solver = "MANIFOLD"
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(other, do_unlink=True)
    return target


def union(target, *others):
    for o in others:
        _boolean(target, o, "UNION")
    return target


def cut(target, *others):
    for o in others:
        _boolean(target, o, "DIFFERENCE")
    return target


def intersect(target, other):
    return _boolean(target, other, "INTERSECT")


def copy(ob, name=None):
    c = ob.copy()
    c.data = ob.data.copy()
    c.name = name or ob.name + "_copy"
    bpy.context.scene.collection.objects.link(c)
    return c


def loft(name, rings):
    """Closed solid through planar rings of equal vertex count, capped at both ends. Each
    pair of neighbouring rings must bound planar side faces (straight, ruled sides)."""
    bm = bmesh.new()
    vs = [[bm.verts.new(Vector(v)) for v in ring] for ring in rings]
    n = len(vs[0])
    bm.faces.new(vs[0])
    bm.faces.new(list(reversed(vs[-1])))
    for a, b in zip(vs, vs[1:]):
        for i in range(n):
            bm.faces.new((a[i], b[i], b[(i + 1) % n], a[(i + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(name, bm)


def bake(ob):
    """Apply the object transform to its mesh."""
    ob.data.transform(ob.matrix_world)
    ob.matrix_world.identity()
    return ob


def apply_print_rotation(ob, deg_xyz):
    """Rotate into print orientation, then put the lowest point on Z = 0, centred in XY."""
    bake(ob)
    ob.data.transform(Euler([math.radians(a) for a in deg_xyz]).to_matrix().to_4x4())
    lo, hi = bbox(ob)
    ob.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    ob.data.update()
    return ob


def bbox(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def non_manifold_edges(ob) -> int:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def volume(ob) -> float:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


def ray_hits(ob, origin, direction, max_dist=1e4):
    """World-space ray cast against one object; returns the hit distance or None."""
    inv = ob.matrix_world.inverted()
    o = inv @ Vector(origin)
    d = (inv.to_3x3() @ Vector(direction)).normalized()
    ok, loc, _, _ = ob.ray_cast(o, d, distance=max_dist)
    return (ob.matrix_world @ loc - Vector(origin)).length if ok else None


def export_stl(ob, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True,
                          global_scale=1.0, apply_modifiers=True, ascii_format=False)
