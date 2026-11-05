# Case: v1 test bed

This directory holds the v1 test bed of esp32-photostation. It is not the final weatherproof
box. It is a plywood corridor with a printed camera module on a rail, so that you can change the
camera height and tilt between tests without reprinting, and measure BLE identification in a real
run. The final box is made from the test results.

The test bed is built for one medium laying hen (about 2 kg). The corridor is a dead end, 250 mm
wide and 400 mm high inside. A bait bowl on the floor holds the hen's head in front of the camera.
The camera looks through an opening in the front wall.

v1 has no PIR. Only BLE starts a visit, so the case has no PIR mount.

Lighting is external: the light is not part of the station or of this case, and it must not
shine into the lens.

The design, the owner decisions and the "done when" list are in
[../../docs/superpowers/specs/2026-11-05-case-testbed-design.md](../../docs/superpowers/specs/2026-11-05-case-testbed-design.md).
Wiring and pin assignments are in [../../docs/hardware.md](../../docs/hardware.md). The antenna
lessons are in [../../docs/hardware.md](../../docs/hardware.md#antenna-lessons).

## Part list

All parts are PETG. The sizes are the bounding boxes of the STL files in `stl/`, in print
orientation (x by y by z, mm).

| STL | Count | Print orientation | Size | What it does |
|---|---|---|---|---|
| `rail.stl` | 2 | Front face down, long axis flat | 24 x 249 x 9 | Vertical rail on the outside of the front wall. A slot guides the carriage tongue and the M5 bolt. Tick marks every 10 mm on both sides of the slot, symmetric about the middle, so one print serves both rails. |
| `carriage.stl` | 1 | Upright, Z up, bottom bar on the bed | 136 x 28.5 x 102 | Rides both rails. Its two cheeks hold the module on the pivot and on the tilt index holes. |
| `module_body.stl` | 1 | Top face down | 64 x 49.5 x 81 | Box for the camera and the electronics. Open at the rear. |
| `module_lid.stl` | 1 | Outer face down | 64 x 78 x 28.4 | Closes the rear. Holds the silica gel bag and pushes the sled to its stop. Louvres instead of a hood. |
| `board_sled.stl` | 1 | Bottom edge down, plate upright | 58.6 x 4.4 x 26 | Carries the XIAO board on its front. |
| `window_frame.stl` | 1 | Front face down | 56 x 45.5 x 4 | Holds the acrylic pane. Slides down into the guides on the body. |
| `bowl_holder.stl` | 1 | Flat, ring on the bed | 174.4 x 183.6 x 20 | Ring with three screw tabs. Its bore tapers with the bowl wall, so the bowl seats in it. Fixes the bowl in one place. |
| `antenna_holder.stl` | 1 | Pocket side up | 50 x 130 x 4 | Plate under the roof for the FPC antenna. Slots let you move it back and forth. |
| `cable_clip.stl` | 3 | Groove side up | 12 x 20 x 6 | Guides the u.FL extension cable along the roof. |
| `coupon_rail.stl` | 1 | As exported | 53 x 40 x 9 | Fit coupon: rail slot and carriage tongue. |
| `coupon_window.stl` | 1 | As exported | 125 x 20 x 50 | Fit coupon: window guides and frame. |
| `coupon_sled.stl` | 1 | As exported | 16.4 x 30.2 x 34 | Fit coupon: sled groove and sled edge. |

Every part fits the 250 mm limit of the P1S bed and prints without supports.

## Print settings

- Printer: Bambu Lab P1S, 0.4 mm nozzle.
- Profile: 0.16 mm Optimal, PETG Basic. PLA softens at 42 C; do not use it.
- Walls: 3 loops. No supports.
- Print the three coupons first. Check the sliding fits (rail and tongue, frame in the guides, sled
  in the grooves). The design assumes 0.3 mm clearance per side. If a fit is too tight or too
  loose, change `clr` in `cad/params.py` and rebuild (see Rebuilding).

## Hardware (BOM)

| Item | Count | Use |
|---|---|---|
| M4 x 16 self-tapping screw | 2 | Pivot, through the carriage cheeks into the module |
| M3 x 12 self-tapping screw | 2 | Tilt index. Cheek 6 mm + gap 1 mm + pilot 8.4 mm (wall and boss) = 15.4 mm at most; 12 mm gives 5 mm of thread in the body. |
| M3 x 10 self-tapping screw | 2 | Lid. Lid 2.4 mm + pilot 8 mm = 10.4 mm at most. |
| M5 hex bolt, M5 x 25, with washer and wing nut | 2 | Rail clamp. The head sits in the rail channel; the clamped stack is the rail skin 4.5 mm + the carriage plate 6 mm = 10.5 mm, plus the washer and the wing nut. |
| 4 x 20 wood screw, countersunk | 4 | Rails. Rail 9 mm + wall 12 mm = 21 mm at most. The printed holes are D4.5. |
| 4 x 16 wood screw, countersunk | 3 | Bowl holder. Tab 5 mm + floor 12 mm = 17 mm at most. The printed holes are D4.5. |
| M4 nylon bolt and nylon wing nut | 2 | Antenna holder. Nylon only: no metal near the antenna. |
| Clear acrylic or PC pane, 20 x 20 x 2 mm | 1 | Window in front of the lens |
| Zip tie | 1 | Strain relief for the USB-C cable |
| Silica gel bag, 30 x 20 x 10 mm | 1 | In the lid cage |
| u.FL (IPEX) 1.13 extension cable | 1 | Module to antenna. See the length warning below. |
| Seeed 2.4 GHz FPC antenna | 1 | Already part of the station |
| Plywood, 12 mm | 1 set | Corridor. See the cut list. |

Cable clips: fix the three clips with glue or tape, or with 4 mm wood screws that stay at least
100 mm from the antenna radiator.

### u.FL extension length

The design spec says 15 to 20 cm. That does not reach. `params.antenna_cable_mm` computes the real
route: module top, up outside the front wall, over the roof to the roof hole, through the roof,
along the underside to the antenna, plus 50 mm slack.

- Worst case, rail low (pivot at 125 mm): 676 mm.
- Rail high (pivot at 315 mm): 486 mm.

Buy an extension cable of at least 70 cm. Or move the antenna holder towards the front wall (set
`antenna_y` in `cad/params.py` and rebuild) to shorten the route.

## Plywood cut list

All boards are 12 mm plywood. The corridor is 250 mm wide, 400 mm high and 650 mm long inside. The
entrance end is open. The floor and the roof span the full width, the side walls stand on the floor,
and the front wall sits between the side walls.

| Board | Count | Length (mm) | Width (mm) | Thickness (mm) |
|---|---|---|---|---|
| `wood_floor` | 1 | 662 | 274 | 12 |
| `wood_roof` | 1 | 662 | 274 | 12 |
| `wood_side` | 2 | 662 | 400 | 12 |
| `wood_front` | 1 | 400 | 250 | 12 |

Openings and drill positions. Measure each one from the edges named in the note.

- `wood_front`: opening 80 x 345, centred across, from 30 to 375 above the bottom edge.
- `wood_front`: on the inner face, a 45 deg bevel 6.5 deep on the two side edges and the bottom
  edge of the opening (not the top), so the opening measures 93 x 351.5 on the inner face. At the
  high position the steep lower corners of the image pass the side faces just inside the wall;
  without the bevel they are cut off. The bevel leaves 7.25 mm of wood beside each rail screw hole.
- `wood_front`: rail screws, 4 x pilot for 4 x 20 wood screws at (69, 64.5), (69, 295.5), (181, 64.5),
  (181, 295.5) (from the left edge, from the bottom edge; outer face).
- `wood_roof`: u.FL hole D6 at (137, 22) (from the left edge, from the front edge).
- `wood_roof`: antenna holder, 2 x D4.5 for M4 nylon bolts at (119, 312) and (155, 312) (from the left
  edge, from the front edge). Nylon only, no metal within 100 mm of the radiator.
- `wood_floor`: bowl holder, 3 x pilot for 4 x 16 wood screws at (137, 287.3), (58.8, 151.8) and (215.2, 151.8)
  (from the left edge, from the front edge).

`blender.sh build.py` prints the same list. If the code and this table differ, the code is right.

## Assembly

1. Screw the two rails to the outside of the front wall at the four drill positions. The second
   rail is the same print as the first, turned end for end.
2. Put one M5 bolt into each rail channel. The head sits in the channel, the shank goes through the
   slot.
3. Push the carriage onto the two bolts. The tongues enter the slots. Add the washers and the wing
   nuts, but do not tighten them.
4. Put the XIAO board into the pocket on the front of the sled.
5. Slide the sled into the grooves in the body from the rear, until it stops. Leave the USB-C hole
   at the bottom free.
6. Put the silica gel bag into the cage of the lid. Fit the lid with the two M3 screws.
7. Press the acrylic pane into the window frame. Slide the frame down into the guides on the body
   front, from above.
8. Hold the module between the carriage cheeks. Fit the two M4 pivot screws into the side bosses.
9. Fit one M3 index screw through the cheek hole for the tilt you want (0, 15, 30 or 45 degrees).
10. Fit the antenna holder under the roof with the two M4 nylon bolts and nylon wing nuts. Stick the
    FPC antenna into its pocket.
11. Run the u.FL extension cable from the module top slot, up outside the front wall, over the roof
    and through the D6 roof hole. Lay it along the underside of the roof in the three clips to the
    antenna holder.
12. Bring the USB-C cable up through the bottom hole of the module. Fix it to the anchor bar with
    the zip tie. Let it hang in a drip loop below the anchor.
13. Fit the bowl holder on the floor with three wood screws. Put the bowl into it.
14. Set the camera height and tilt (next section) and tighten the wing nuts.

## Setting the camera

The rail has three planned positions. Each is a pivot height with a matching tilt. The tick marks
on the rail (every 10 mm on both sides of the slot, a long tick every 50 mm from the middle) help
you repeat a height. The bolt centre on the middle long tick is the mid position; the low and high
positions put it halfway between two ticks (85 and 275 mm above the floor).

| Rail position | Pivot height (mm) | Tilt (degrees) | Distance lens to head (mm) |
|---|---|---|---|
| Low | 125 | 0 | 205 |
| Mid | 220 | 30 | 237 |
| High | 315 | 45 | 296 |

The distances are for a head 100 mm above the floor (bowl 60 mm high, head centre 40 mm above the
rim) and the bowl centre 185 mm from the front wall. Measure your bowl and change `params.py` if
yours differs.

To clean the window, lift the window frame straight up out of its guides.

- At tilt 0 or 15 the frame lifts out.
- At tilt 30 or 45 the frame cannot lift out. First set the tilt to 0, then lift the frame out.

`station-case.blend` shows the mid position at tilt 30. In Blender, move the empty
`carriage_origin` for the rail height and rotate `module_pivot` for the tilt.

## Limits found

- The head is about 190 to 270 px wide in a 2048 px image (189 px at the high position, 273 px at
  the low one). For a portrait, crop the image.
- At the high position (tilt 45) the module clears the wall by only 1.0 mm.
- The central 60% of the image (in each direction) is clear at every position. The front wall,
  rails, carriage and module block 0% of the whole frame at the low position, 1.4% at mid and
  20.8% at high, where the lower left and right of the image see the side faces of the opening.
  The opening bevel keeps the lower corners of the central 60% clear at the high position.
- The window frame lifts out only at tilt 15 or less.
- The u.FL cable length is 486 to 676 mm, not 15 to 20 cm (see above).

## Measure before printing

Some values in [ref/DIMENSIONS.md](ref/DIMENSIONS.md) come from a model or a third party. Measure
these with calipers on the real parts, then change `cad/params.py` and rebuild:

1. The bowl: diameter, rim height and foot.
2. The real height of the XIAO stack (wiki: 15 mm, model: 13.96 mm) and the board thickness.
3. How far the microSD card sticks out of the expansion board, with a card inserted.
4. The head length and width of the USB-C plug, and the cable diameter.
5. The real size of the antenna and the length of its cable.

## Rebuilding

The model is a set of Python scripts that run in Blender 5.2. `cad/params.py` holds every
dimension and needs no Blender. The files in `stl/` and `station-case.blend` are generated. Never
edit them by hand: change `cad/params.py` or a part in `cad/parts/`, then rebuild.

```sh
hardware/case/cad/blender.sh build.py          # writes stl/*.stl and station-case.blend
hardware/case/cad/blender.sh verify.py         # fit, interference, field of view, metal clearance
python3 -I hardware/case/cad/slice_check.py    # slices every STL with the Bambu Studio CLI
hardware/case/cad/blender.sh check_part.py rail    # checks one part
python3 -m unittest discover -s hardware/case/cad -p 'test_*.py'   # host tests, no Blender
```

Set `BLENDER` to use a Blender binary outside `/Applications`. `slice_check.py` skips with a short
message when Bambu Studio is not installed. A failing `verify.py` check is fixed in `params.py` or
in the part, never by loosening the check.

## Mechanical reference data

[ref/DIMENSIONS.md](ref/DIMENSIONS.md) collects the dimensions of the parts the case must hold:
the XIAO ESP32S3 Sense stack, the camera modules, the FPC antenna, the AM312 PIR, the LED strip,
the microSD card and the USB-C plug. Each value says whether it comes from an official drawing, a
3D model, a third party or an estimate, and links its source.

The datasheets and vendor CAD files themselves are not in the repository, because their licenses
do not clearly allow redistribution. Download them from the linked sources into `ref/` (the
directory is gitignored except for `DIMENSIONS.md`).

## How to contribute

1. Open an issue with photos or a sketch of your case and the animal you built it for.
2. Add the source model (STEP, FreeCAD, OpenSCAD or similar) next to the exported STL, so the
   next person can change it.
3. State the print settings you used (material, layer height, infill, supports) in this README.
4. Keep file names generic (`station-case`, `electronics-tray`); the animal is a parameter, not
   the identity of the project.

The case files are published under the project's MIT license, like the rest of the repository.
