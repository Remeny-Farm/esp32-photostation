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
from params import P, head_center  # noqa: E402
from parts import board_sled  # noqa: E402

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
    usb_y1 = y0 + pcb_t + 4.2
    usbc_z0 = z_bot - p.usbc_overhang
    usbc = mesh.box_span("ph_usbc", (-8.94 / 2, 8.94 / 2), (y0 + pcb_t, usb_y1), (usbc_z0, usbc_z0 + 7.3))
    ufl = mesh.box_span("ph_ufl", (-1.5, 1.5), (y0 + pcb_t, y0 + 2 * pcb_t), (z_top - 3.5, z_top - 0.5))
    mesh.union(xiao, sense, usbc, ufl)

    # Camera module behind the lens: 8 x 8 holder, then the lens barrel to the lens front.
    lx, ly, lz = p.lens
    depth = p.cam_module[1]
    cw, ch = p.cam_module[0], p.cam_module[2]
    holder_y1 = ly - 2.0
    cam = mesh.box_span("ph_camera", (lx - cw / 2, lx + cw / 2), (ly - depth, holder_y1),
                        (lz - ch / 2, lz + ch / 2))
    lens = mesh.cyl("ph_lens", 6.2, ly - holder_y1, (lx, (ly + holder_y1) / 2, lz), axis="Y")
    mesh.union(cam, lens)

    # USB-C overmould directly below the receptacle, then the cable continuing down.
    mw, mt, ml = p.usb_mould
    cx, cy = 0.0, (y0 + pcb_t + usb_y1) / 2
    mould = mesh.box_span("ph_usb", (cx - mw / 2, cx + mw / 2), (cy - mt / 2, cy + mt / 2),
                          (usbc_z0 - ml, usbc_z0))
    cable_len = 40.0
    cable = mesh.cyl("ph_usb_cable", p.usb_cable_d, cable_len, (cx, cy, usbc_z0 - ml - cable_len / 2))
    mesh.union(mould, cable)

    # Perfboard on the rear face of the sled, standing on the sled's seat ledge (the same
    # place board_sled.perfboard_box gives the lid checks), with its component block behind it.
    pw, pt, ph = p.perfboard
    sled_rear = p.board_back_y - p.sled_t
    zc = board_sled.perfboard_box(p)[2][0] + ph / 2
    perf = mesh.box_span("ph_perfboard", (-pw / 2, pw / 2), (sled_rear - pt, sled_rear),
                         (zc - ph / 2, zc + ph / 2))
    blk = mesh.box_span("ph_perf_parts", (-8.0, 8.0), (sled_rear - pt - p.perf_parts_h, sled_rear - pt),
                        (zc - 10.0, zc + 10.0))
    mesh.union(perf, blk)

    # LED strips in the front pockets, 0.3 mm behind the body front face.
    sw, st, sl = p.led_strip
    y1 = p.mod_y0 - 0.3
    leds = [mesh.box_span(n, (sx - sw / 2, sx + sw / 2), (y1 - st, y1), (lz - sl / 2, lz + sl / 2))
            for n, sx in (("ph_led_l", -p.led_x), ("ph_led_r", p.led_x))]
    return _collect([xiao, cam, mould, perf] + leds)


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
    names = ["ph_xiao", "ph_camera", "ph_usb", "ph_perfboard"]
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
