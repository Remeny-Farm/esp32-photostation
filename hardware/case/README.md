# Case

This directory will hold the 3D-printed case of esp32-photostation. No model files are published
yet; this page records the design the firmware and hardware assume, so that a contributed case
fits them.

## Design sketch

- A single-animal corridor: one animal fits inside at a time. The width and height follow the
  animal; for a hen the entrance is about 20-25 cm.
- A bait bowl at the far end. The animal walks in, lowers its head to the bowl and stays for a
  few seconds, which is the visit the station photographs.
- The camera sits above and behind the bait bowl, looking at the animal's head at a distance of
  20-30 cm. Check the field of view with a cardboard mock-up before printing; a wide-angle lens
  may be needed for close-ups.
- The electronics compartment is on the roof: the XIAO board, the PIR, the MOSFET and the cable
  entry. The compartment is closed against dust and ammonia and holds a silica gel bag.
- A cleanable acrylic or polycarbonate window in front of the camera, replaceable from outside.
- The u.FL antenna is fixed to the inside of the roof, above the animal's back, where the tag of
  the animal inside is closest to it. No metal near the antenna.
- Ventilation and shade: the case must work at 42 C in the shade. Print it in PETG (PLA softens),
  add vents above the electronics and a roof overhang or a separate shade.
- The PIR looks down the corridor from the roof or the back wall so that it fires when the animal
  is near the bowl, not when it passes outside the entrance.
- The light (LED strip with a diffuser) sits around the camera window and lights the head without
  shining into the lens.

Optional: aluminium tape on the inside walls, as described in
[../../docs/hardware.md](../../docs/hardware.md#antenna-lessons); try without it first.

Wiring and pin assignments are in [../../docs/hardware.md](../../docs/hardware.md).

## Planned files

- `station-case.step` and `station-case.stl`: the body, roof and window frame as printable
  parts.
- `electronics-tray.step` / `.stl`: the tray for the board, PIR and MOSFET.
- `README.md` (this file): print settings and assembly notes once the parts exist.

## How to contribute

1. Open an issue with photos or a sketch of your case and the animal you built it for.
2. Add the source model (STEP, FreeCAD, OpenSCAD or similar) next to the exported STL, so the
   next person can change it.
3. State the print settings you used (material, layer height, infill, supports) in this README.
4. Keep file names generic (`station-case`, `electronics-tray`); the animal is a parameter, not
   the identity of the project.

The case files are published under the project's MIT license, like the rest of the repository.
