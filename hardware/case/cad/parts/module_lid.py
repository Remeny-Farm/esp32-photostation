"""Rear lid of the camera module (module local frame, see params.py).

A plate over the open rear of module_body with a rim that locates it in the cavity, two M3
self-tapping screws into the body's corner pilots, a silica gel cage, two ribs that push the
board sled against its stop, and vent slots near the top.

Print orientation: outer face on the bed. An outside hood cannot be printed that way (it would
hang below the bed), so the vents are 45 deg louvres through the plate instead: the outer
opening sits lower than the inner one, which gives the hood's rain and dust shadow without a
part outside the plate.
"""

import bpy

import mesh
from parts import board_sled as sled
from parts import module_body as body

PRINT_ROT = (90.0, 0.0, 0.0)
COUNT = 1

RIM_T = 1.6          # rim thickness (4 lines)
RIM_H = 1.5
CAGE_T = 1.2         # cage wall
CAGE_IN = (31.0, 20.5, 10.5)  # silica bag 30 x 20 x 10 (x, y, z) plus 0.5 to slide it in
CAGE_Z0 = -49.0      # cage inner bottom: above the bottom chamfers, below the perfboard
SLOT_W = 2.0
GRILLE_X = (-12.5, -7.5, -2.5, 2.5, 7.5, 12.5)
PUSH_X = (23.0, 25.0)  # push ribs: clear of the perfboard clips and the side-wall ribs
PUSH_Z = (-30.0, -12.0)
LOUVRE_Z = (-3.2, -7.7, -12.2)  # outer bottom edge of each vent
LOUVRE_X = 10.0
LOUVRE_H = 2.0
E = 0.1


def _cage(p):
    yi = p.mod_y1
    cx, cy, cz = CAGE_IN
    t = CAGE_T
    z0, z1 = CAGE_Z0, CAGE_Z0 + cz
    cage = mesh.box_span("cage", (-cx / 2 - t, cx / 2 + t), (yi - E, yi + cy + t),
                         (z0 - t, z1 + t))
    # Open at +x: the bag slides in sideways. The cut stops at the plate face.
    mesh.cut(cage, mesh.box_span("cage_in", (-cx / 2, cx / 2 + t + 1), (yi, yi + cy), (z0, z1)))
    slots = []
    for x in GRILLE_X:
        # Front grille: bars span z (10.5 mm bridges in print).
        slots.append(mesh.box_span("grille", (x - SLOT_W / 2, x + SLOT_W / 2),
                                   (yi + cy - 1, yi + cy + t + 1), (z0 + 0.5, z1 - 0.5)))
        # Top and bottom walls: slots along y, vertical in print.
        for za, zb in ((z0 - t - 1, z0 + 0.5), (z1 - 0.5, z1 + t + 1)):
            slots.append(mesh.box_span("wall_slot", (x - SLOT_W / 2, x + SLOT_W / 2),
                                       (yi + 2, yi + cy - 2), (za, zb)))
    for z in (z0 + 1.5, z1 - 1.5 - SLOT_W):
        slots.append(mesh.box_span("side_slot", (-cx / 2 - t - 1, -cx / 2 + 1),
                                   (yi + 2, yi + cy - 2), (z, z + SLOT_W)))
    mesh.cut(cage, *slots)
    return cage


def build(p):
    yi, yo = p.mod_y1, p.mod_y1 - p.wall
    ob = mesh.box_span("module_lid", (-p.mod_x, p.mod_x), (yo, yi), (p.mod_z0, p.mod_z1))

    cav = body.cavity(p)
    rim = body.prism("rim", body.inset(cav, p.clr), "Y", yi - E, yi + RIM_H)
    mesh.cut(rim, body.prism("rim_in", body.inset(cav, p.clr + RIM_T), "Y", yi - 2 * E,
                             yi + RIM_H + 1))

    push = [mesh.box_span("push_rib", (s * PUSH_X[0], s * PUSH_X[1]),
                          (yi - E, p.board_back_y - p.sled_t), PUSH_Z) for s in (-1, 1)]
    mesh.union(ob, rim, _cage(p), *push)

    cuts = [mesh.cyl("screw_hole", p.lid_screw_clear_d, p.wall + 2, (bx, yi - p.wall / 2, bz),
                     "Y", 32) for bx, bz in body.lid_bosses(p)]
    rise = p.wall + 2 * E    # 45 deg: the vent climbs as much as it goes through
    for z in LOUVRE_Z:
        cuts.append(body.prism("louvre", [(yo - E, z), (yi + E, z + rise),
                                          (yi + E, z + rise + LOUVRE_H), (yo - E, z + LOUVRE_H)],
                               "X", -LOUVRE_X, LOUVRE_X))
    mesh.cut(ob, *cuts)
    return ob


def _overlap(a_ob, b_ob):
    """Volume of a_ob ∩ b_ob; b_ob is consumed."""
    tmp = mesh.copy(a_ob, "overlap_tmp")
    mesh.intersect(tmp, b_ob)
    v = mesh.volume(tmp)
    bpy.data.objects.remove(tmp, do_unlink=True)
    return v


def checks(p, ob):
    bpy.context.view_layer.update()
    errs = []

    def ray(o, d):
        return mesh.ray_hits(ob, o, d)

    def near(name, got, want, tol=0.05):
        if got is None or abs(got - want) > tol:
            errs.append(f"{name}: {None if got is None else round(got, 3)}, want {want:g}")

    # Screw holes on the body's pilot axes.
    ym = p.mod_y1 - p.wall / 2
    for bx, bz in body.lid_bosses(p):
        for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)):
            near(f"lid hole ({bx:g}, {bz:g}) radius {d}", ray((bx, ym, bz), d),
                 p.lid_screw_clear_d / 2)
        if ray((bx, ym - 10, bz), (0, 1, 0)) is not None:
            errs.append(f"lid hole ({bx:g}, {bz:g}) is blocked")

    # Rim fits inside the body walls with the sliding clearance.
    near("rim outer face", ray((40, p.mod_y1 + 0.75, -20), (-1, 0, 0)),
         40 - (body.inner_x(p) - p.clr))

    # Push ribs end on the sled rear face.
    lo, hi = mesh.bbox(ob)
    near("push ribs reach the sled rear face", hi.y, p.board_back_y - p.sled_t, 0.01)
    for s in (-1, 1):
        near(f"push rib x={s:+d}", ray((s * 24, p.board_back_y, -21), (0, -1, 0)), p.sled_t,
             0.01)

    # Silica cage: walls on five sides, a 30 x 20 x 10 bag fits inside untouched.
    cx, cy, cz = CAGE_IN
    c = (0.0, p.mod_y1 + cy / 2, CAGE_Z0 + cz / 2)
    near("cage side wall", ray(c, (-1, 0, 0)), cx / 2)
    near("cage top wall", ray(c, (0, 0, 1)), cz / 2)
    near("cage bottom wall", ray(c, (0, 0, -1)), cz / 2)
    near("cage grille", ray(c, (0, 1, 0)), cy / 2)
    near("cage back (lid face)", ray(c, (0, -1, 0)), cy / 2)
    bag = mesh.box("silica_probe", (30.0, 20.0, 10.0), c)
    v = _overlap(ob, bag)
    if v > 1e-3:
        errs.append(f"silica bag 30 x 20 x 10 overlaps the cage by {v:.2f} mm3")

    # Nothing of the lid may meet the perfboard (with its parts) or the body.
    perf = sled.perfboard_box(p)
    v = _overlap(ob, mesh.box_span("perf_probe", *perf))
    if v > 1e-3:
        errs.append(f"lid meets the perfboard space: {v:.2f} mm3")
    v = _overlap(ob, body.build(p))
    if v > 1e-3:
        errs.append(f"lid meets the body: {v:.2f} mm3")

    errs += body.overhang_errors(ob, PRINT_ROT)
    return errs
