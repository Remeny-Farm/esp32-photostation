"""Non-printed placeholders: electronics, bowl, hen head and antenna radiator.

They only exist to check fit and field of view, so they use the measured or datasheet
envelopes from DIMENSIONS.md, not vendor CAD. All objects are named ph_* and live in the
`placeholders` collection.

Run as a script (blender.sh components.py) to print every bbox and check that the
electronics do not overlap each other.
"""

import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mesh  # noqa: E402
from params import P, camera_box, head_center, usb_plug_box  # noqa: E402

COLLECTION = "placeholders"


def _collect(objs):
    """Move objects into the `placeholders` collection (created on first use)."""
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        bpy.context.scene.collection.children.link(col)
    for ob in objs:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        col.objects.link(ob)
    return objs


def _sphere(name, d, center, segments=48):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=d / 2)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return mesh._obj(name, bm)


def build_module_parts(p: P):
    """Electronics in the module local frame (origin at the tilt pivot)."""
    # XIAO ESP32S3 Sense stack. The length axis is vertical, u.FL end up, USB-C down.
    pcb_t = 1.25
    y0 = p.board_back_y
    z_top = p.board_z1
    z_bot = z_top - p.board_len
    xiao = mesh.box_span("ph_xiao", (-p.board_w / 2, p.board_w / 2), (y0, y0 + pcb_t), (z_bot, z_top))
    sense_y = y0 + pcb_t + 2.93
    sense_top = z_top - 0.30
    sense = mesh.box_span("ph_xiao_sense", (-16.78 / 2, 16.78 / 2), (sense_y, sense_y + pcb_t),
                          (sense_top - 14.68, sense_top))
    usbc_z0 = z_bot - p.usbc_overhang
    usbc = mesh.box_span("ph_usbc", (-8.94 / 2, 8.94 / 2), (y0 + p.usbc_y[0], y0 + p.usbc_y[1]),
                         (usbc_z0, usbc_z0 + 7.3))
    ufl = mesh.box_span("ph_ufl", (-1.5, 1.5), (y0 + pcb_t, y0 + 2 * pcb_t), (z_top - 3.5, z_top - 0.5))
    mesh.union(xiao, sense, usbc, ufl)

    # Camera module behind the lens: 8 x 8 holder, then the lens barrel to the lens front.
    lx, ly, lz = p.lens
    cam = mesh.box_span("ph_camera", *camera_box(p))
    holder_y1 = camera_box(p)[1][1]
    lens = mesh.cyl("ph_lens", 6.2, ly - holder_y1, (lx, (ly + holder_y1) / 2, lz), axis="Y")
    mesh.union(cam, lens)

    # USB-C overmould directly below the receptacle, then the cable continuing down.
    mx, my, mz = usb_plug_box(p)
    mould = mesh.box_span("ph_usb", mx, my, mz)
    cx, cy = sum(mx) / 2, sum(my) / 2
    cable_len = 40.0
    cable = mesh.cyl("ph_usb_cable", p.usb_cable_d, cable_len, (cx, cy, mz[0] - cable_len / 2))
    mesh.union(mould, cable)

    return _collect([xiao, cam, mould])


def build_world_parts(p: P):
    """Bowl, hen head and antenna radiator in the world frame."""
    # Bowl: hollow truncated cone, wall 3 and floor 3.
    wall = floor = 3.0
    h = p.bowl_h

    def dia(z):
        return p.bowl_d_base + (p.bowl_d_top - p.bowl_d_base) * z / h

    bowl = mesh.cone("ph_bowl", p.bowl_d_base, p.bowl_d_top, h, (0, p.bowl_y, h / 2))
    z0, z1 = floor, h + 1.0  # the cut overshoots the rim so no skin is left
    inner = mesh.cone("ph_bowl_in", dia(z0) - 2 * wall, dia(z1) - 2 * wall, z1 - z0,
                      (0, p.bowl_y, (z0 + z1) / 2))
    mesh.cut(bowl, inner)

    head = _sphere("ph_head", p.head_d, head_center(p))

    ax, ay, az = p.antenna_fpc
    top = p.inner_h - (p.ant_plate[2] - p.ant_pocket_depth)
    ant = mesh.box_span("ph_antenna", (-ax / 2, ax / 2), (p.antenna_y - ay / 2, p.antenna_y + ay / 2),
                        (top - az, top))
    return _collect([bowl, head, ant])


def _overlap_mm3(a, b):
    """Overlap volume of two objects, measured on copies so the originals stay intact."""
    ca = mesh.copy(a, "_ov_a")
    cb = mesh.copy(b, "_ov_b")
    mesh.intersect(ca, cb)
    v = abs(mesh.volume(ca))
    bpy.data.objects.remove(ca, do_unlink=True)
    return v


def main():
    mesh.reset_scene()
    p = P()
    mod = build_module_parts(p)
    world = build_world_parts(p)
    for ob in mod + world:
        lo, hi = mesh.bbox(ob)
        print(f"{ob.name}: bbox ({lo.x:.2f}, {lo.y:.2f}, {lo.z:.2f}) .. ({hi.x:.2f}, {hi.y:.2f}, {hi.z:.2f})")

    byname = {o.name: o for o in mod}
    names = ["ph_xiao", "ph_camera", "ph_usb"]
    ok = True
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = _overlap_mm3(byname[a], byname[b])
            if v >= 1.0:
                print(f"FAIL overlap {a} / {b}: {v:.2f} mm3")
                ok = False
    if not ok:
        sys.exit(1)
    print("OK components")


if __name__ == "__main__":
    main()
