"""Build one part and check it is printable: blender.sh check_part.py <name> [--set k=v ...]

Exit 1 unless the mesh is manifold, has volume, fits the bed in its print orientation
and passes the part's own checks().
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mesh  # noqa: E402
from params import P  # noqa: E402
from parts import load  # noqa: E402


def overrides(argv):
    kw = {}
    for i, a in enumerate(argv):
        if a == "--set":
            k, v = argv[i + 1].split("=", 1)
            kw[k] = float(v)  # scalar fields only
    return kw


def check(name, p):
    mesh.reset_scene()
    mod = load(name)
    ob = mod.build(p)
    errs = list(mod.checks(p, ob)) if hasattr(mod, "checks") else []
    mesh.apply_print_rotation(ob, mod.PRINT_ROT)
    nm = mesh.non_manifold_edges(ob)
    if nm:
        errs.append(f"{nm} non-manifold edges")
    vol = mesh.volume(ob)
    if vol <= 0:
        errs.append(f"volume {vol:.1f}")
    lo, hi = mesh.bbox(ob)
    size = hi - lo
    if max(size) > p.bed:
        errs.append(f"print size {size.x:.1f} x {size.y:.1f} x {size.z:.1f} exceeds {p.bed}")
    if abs(lo.z) > 1e-3:
        errs.append(f"lowest point z={lo.z:.3f}, not on the bed")
    return errs, size, vol


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    name = argv[0]
    p = P().with_(**overrides(argv[1:]))
    errs, size, vol = check(name, p)
    if errs:
        for e in errs:
            print(f"FAIL {name}: {e}")
        sys.exit(1)
    print(f"OK {name}: {size.x:.1f} x {size.y:.1f} x {size.z:.1f} mm, {vol / 1000:.1f} cm3")


if __name__ == "__main__":
    main()
