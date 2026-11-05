"""Rebuild every generated file: blender.sh build.py

  hardware/case/stl/<part>.stl     one per part in PARTS and per coupon, in print orientation
  hardware/case/station-case.blend the assembly at rail state "mid" and its nearest tilt

Then prints the plywood cut list and the u.FL extension length. Exit 1 if a part or a
coupon is not printable (non-manifold, off the bed, larger than the bed).
"""

import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import assembly  # noqa: E402
import coupon  # noqa: E402
import mesh  # noqa: E402
from params import P, RAIL_PIVOT_Z, aim_tilt, antenna_cable_mm, nearest_tilt  # noqa: E402
from parts import PARTS, load  # noqa: E402

CASE = HERE.parent
STL = CASE / "stl"
BLEND = CASE / "station-case.blend"


def _printable(name, ob, p):
    errs = []
    nm = mesh.non_manifold_edges(ob)
    if nm:
        errs.append(f"{nm} non-manifold edges")
    lo, hi = mesh.bbox(ob)
    size = hi - lo
    if max(size) > p.bed:
        errs.append(f"print size {size.x:.1f} x {size.y:.1f} x {size.z:.1f} exceeds {p.bed}")
    if abs(lo.z) > 1e-3:
        errs.append(f"lowest point z={lo.z:.3f}")
    for e in errs:
        print(f"FAIL {name}: {e}")
    if not errs:
        print(f"stl/{name}.stl  {size.x:.1f} x {size.y:.1f} x {size.z:.1f} mm, "
              f"{mesh.volume(ob) / 1000:.1f} cm3")
    return not errs


def main():
    p = P()
    ok = True
    STL.mkdir(parents=True, exist_ok=True)
    for name in PARTS:
        mesh.reset_scene()
        mod = load(name)
        ob = mod.build(p)
        mesh.apply_print_rotation(ob, mod.PRINT_ROT)
        ok &= _printable(name, ob, p)
        mesh.export_stl(ob, STL / f"{name}.stl")

    mesh.reset_scene()
    for name, ob in coupon.build(p).items():
        errs = coupon.checks(p, ob)
        for e in errs:
            print(f"FAIL {name}: {e}")
        ok &= not errs and _printable(name, ob, p)
        mesh.export_stl(ob, STL / f"{name}.stl")

    mesh.reset_scene()
    tilt = nearest_tilt(aim_tilt(p, RAIL_PIVOT_Z["mid"]))
    assembly.build(p, "mid", tilt)
    bpy.context.preferences.filepaths.use_relative_paths = True
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True, relative_remap=True)
    print(f"saved {BLEND.relative_to(CASE.parent.parent)} (mid, tilt {tilt})")

    print("\nPlywood cut list (mm)")
    print(f"{'board':<12} {'qty':>3} {'length':>7} {'width':>7} {'thick':>6}")
    for name, qty, ln, w, t in assembly.cut_list(p):
        print(f"{name:<12} {qty:>3} {ln:>7.0f} {w:>7.0f} {t:>6.0f}")
    for note in assembly.cut_notes(p):
        print(f"  - {note}")

    worst = max(RAIL_PIVOT_Z, key=lambda s: antenna_cable_mm(p, RAIL_PIVOT_Z[s]))
    print(f"\nu.FL extension: {antenna_cable_mm(p, RAIL_PIVOT_Z[worst]):.0f} mm "
          f"(worst case, rail state {worst}, incl. 50 mm slack)")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
