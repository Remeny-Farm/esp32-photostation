"""Slice every exported STL with the Bambu Studio CLI and fail on slicer errors.

Run with `python3 -I hardware/case/cad/slice_check.py [part ...] [--keep]`. Uses the
stock Bambu Lab P1S 0.4 nozzle machine, the 0.16 mm process and Bambu PETG Basic;
`check_part.py` and `verify.py` prove the geometry, this proves the slicer accepts it
without supports. Skips (exit 0, one line) when Bambu Studio is not installed.
After hen-tag-enclosure's cad/slice_check.py.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STL = Path(__file__).resolve().parent.parent / "stl"
APP = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
PROFILES = Path("/Applications/BambuStudio.app/Contents/Resources/profiles/BBL")
MACHINE = PROFILES / "machine/Bambu Lab P1S 0.4 nozzle.json"
PROCESS = "0.16mm Optimal @BBL X1C"
FILAMENT = PROFILES / "filament/Bambu PETG Basic @BBL X1C.json"

# Supports stay off: every part is designed to print without them, and a part
# that needs them shows up as a floating-cantilever warning.
SETTINGS = {"enable_support": "0", "wall_loops": "3"}
BAD = re.compile(r"floating cantilever|CRITICAL|\[error\]", re.I)


def flatten(name: str, kind: str = "process") -> dict:
    d = json.load(open(PROFILES / kind / f"{name}.json"))
    base = flatten(d["inherits"], kind) if "inherits" in d else {}
    base.update({k: v for k, v in d.items() if k != "inherits"})
    return base


def slice_part(stl: Path, work: Path) -> tuple[bool, list[str]]:
    prof = flatten(PROCESS)
    prof.update(SETTINGS)
    prof["name"], prof["from"] = "photostation_case", "User"
    pj = work / "process.json"
    json.dump(prof, open(pj, "w"))
    # The machine profile is flattened too: loaded with its "inherits" unresolved,
    # the CLI keeps a default 200 x 200 x 100 volume and refuses taller parts.
    mach = flatten(MACHINE.stem, "machine")
    mach["name"] = MACHINE.stem  # the process lists compatible printers by name
    mj = work / "machine.json"
    json.dump(mach, open(mj, "w"))
    r = subprocess.run(
        [str(APP), "--debug", "4", "--load-settings", f"{mj};{pj}",
         "--load-filaments", str(FILAMENT), "--arrange", "1", "--slice", "0",
         "--outputdir", str(work), str(stl)],
        capture_output=True, text=True)
    if "--log" in sys.argv:
        print(r.stdout + r.stderr)
    bad = sorted({ln.strip()[-160:] for ln in (r.stdout + r.stderr).splitlines() if BAD.search(ln)})
    return (work / "plate_1.gcode").exists() and r.returncode == 0, bad


def main() -> int:
    if not (APP.exists() and MACHINE.exists() and FILAMENT.exists()):
        print("Bambu Studio not installed; slicer check skipped.")
        return 0
    keep = "--keep" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    stls = [STL / f"{n}.stl" for n in names] if names else sorted(STL.glob("*.stl"))
    if not stls:
        print(f"FAIL no STL files in {STL}; run blender.sh build.py first")
        return 1
    fails = 0
    for stl in stls:
        work = STL.parent / "out" / "slice" / stl.stem if keep else Path(tempfile.mkdtemp())
        if keep:
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True)
        if not stl.exists():
            ok, bad = False, [f"{stl} missing"]
        else:
            ok, bad = slice_part(stl, work)
        if not keep:
            shutil.rmtree(work, ignore_errors=True)
        if ok and not bad:
            print(f"PASS {stl.stem}")
        else:
            fails += 1
            print(f"FAIL {stl.stem}" + ("" if ok else " (no G-code)"))
            for b in bad:
                print(f"     {b}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
