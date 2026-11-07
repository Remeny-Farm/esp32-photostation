"""Board sled of the camera module (module local frame, see params.py).

A plate that slides in from the rear with its side edges in the body's grooves until it meets
the groove stop; the lid's push ribs hold it there. The front face carries the XIAO main PCB in
a rimmed pocket with two edge hooks. The rear face is plain: lighting is external, so the sled
carries no light driver.

Print orientation: bottom edge on the bed (plate upright). The rim and hooks are vertical
extrusions; the only print-down faces are the 0.8 mm rim and lip ends.
"""

import bpy

import mesh
from parts import module_body as body

PRINT_ROT = (0.0, 0.0, 0.0)
COUNT = 1

POCKET = (18.2, 21.4)   # main PCB 17.78 x 20.95 plus about 0.2 per side
POCKET_D = 0.8          # rim height: below the PCB top (1.25), so no part on it is touched
RIM_W = 1.2
PCB_T = 1.25            # main PCB thickness (DIMENSIONS.md section 1, model; measure)
USB_NOTCH = 5.0         # half-width of the gap in the bottom rim for the USB-C receptacle
HOOK_LEN = 6.0          # hook length along z, centred on the pocket
LIP = 0.7               # hook lip overlap
E = 0.1


def half_width(p):
    return body.inner_x(p) - p.clr


def build(p):
    y0 = p.board_back_y
    y1 = y0 - p.sled_t
    zt, zb = p.sled_z
    hw = half_width(p)
    ob = mesh.box_span("board_sled", (-hw, hw), (y1, y0), (zb, zt))

    # Front: pocket rim around the main PCB, open at the bottom for the USB-C receptacle.
    zc = p.board_z1 - p.board_len / 2
    px, pz = POCKET[0] / 2, POCKET[1] / 2
    rim = mesh.box_span("rim", (-(px + RIM_W), px + RIM_W), (y0 - E, y0 + POCKET_D),
                        (max(zb, zc - pz - RIM_W), zc + pz + RIM_W))
    mesh.cut(rim, mesh.box_span("pocket", (-px, px), (y0 - 1, y0 + 1), (zc - pz, zc + pz)),
             mesh.box_span("usb_notch", (-USB_NOTCH, USB_NOTCH), (y0 - 1, y0 + 1),
                           (zb - 1, zc - pz + E)))
    parts = [rim]
    lip_y0 = y0 + PCB_T + 0.1
    for s in (-1, 1):
        hz = (zc - HOOK_LEN / 2, zc + HOOK_LEN / 2)
        parts.append(mesh.box_span("hook_arm", (s * px, s * (px + RIM_W)),
                                   (y0 + POCKET_D - E, lip_y0 + 1.0), hz))
        # Lead-in on the lip: the PCB pushes the arm aside as it goes in.
        parts.append(body.prism("hook_lip", [(s * (px - LIP), lip_y0), (s * (px + E), lip_y0),
                                             (s * (px + E), lip_y0 + 1.0), (s * px, lip_y0 + 1.0)],
                                "Z", *hz))
    mesh.union(ob, *parts)
    return ob


def checks(p, ob):
    bpy.context.view_layer.update()
    errs = []

    def ray(o, d):
        return mesh.ray_hits(ob, o, d)

    def near(name, got, want, tol=0.05):
        if got is None or abs(got - want) > tol:
            errs.append(f"{name}: {None if got is None else round(got, 3)}, want {want:g}")

    y0 = p.board_back_y
    zc = p.board_z1 - p.board_len / 2
    yr = y0 + POCKET_D / 2            # inside the pocket rim
    a, b = ray((0, yr, zc), (1, 0, 0)), ray((0, yr, zc), (-1, 0, 0))
    near("board pocket width", None if a is None or b is None else a + b, POCKET[0])
    a, b = ray((7, yr, zc), (0, 0, 1)), ray((7, yr, zc), (0, 0, -1))
    near("board pocket length", None if a is None or b is None else a + b, POCKET[1])
    for s in (-1, 1):
        got = ray((s * (POCKET[0] / 2 - 0.3), y0 + 5, zc), (0, -1, 0))
        if got is None or got > 5 - PCB_T - 0.05:
            errs.append(f"no edge hook over the PCB at x={s:+d} ({got})")

    # Plain rear face: nothing stands behind the plate.
    lo, hi = mesh.bbox(ob)
    near("rear face", lo.y, y0 - p.sled_t, 0.01)

    ym = y0 - p.sled_t / 2
    a, b = ray((40, ym, -21), (-1, 0, 0)), ray((-40, ym, -21), (1, 0, 0))
    near("sled width = groove width - 2 clr", None if a is None or b is None else 80 - a - b,
         2 * body.inner_x(p) - 2 * p.clr)

    if lo.z < p.sled_z[1] - 1e-3:
        errs.append(f"sled reaches z {lo.z:.2f}, below {p.sled_z[1]:g} (USB-C overmould)")

    # Slides in the body without touching it.
    tmp = mesh.copy(ob, "overlap_tmp")
    mesh.intersect(tmp, body.build(p))
    v = mesh.volume(tmp)
    bpy.data.objects.remove(tmp, do_unlink=True)
    if v > 1e-3:
        errs.append(f"sled meets the body: {v:.2f} mm3")

    errs += body.overhang_errors(ob, PRINT_ROT)
    return errs
