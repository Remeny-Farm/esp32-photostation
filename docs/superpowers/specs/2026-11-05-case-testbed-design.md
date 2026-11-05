# Photo station case - v1 test bed (design)

Date: 2026-11-05. Status: approved by the owner (2026-11-05).
Related: `docs/2026-11-03-fotoallomas-design.md` (section 9, box sketch),
`hardware/case/README.md`, `hardware/case/ref/DIMENSIONS.md` (part sizes with sources).

## 1. Intent

If a hen walks up, the station takes a photo of it. According to the owner, physical tests
decide how the photo starts and what the layout should be. So the first printed case is a
**test bed**: the camera position can change without reprinting, and BLE identification (M2
milestone) can be measured in a real setting. The final weatherproof box (M4) is made from
the test results, in a separate round.

## 2. Goals, non-goals, anti-goals

Goals:
- A medium laying hybrid walks easily into the corridor, bends to the bowl, and while doing
  so the camera takes a face-on portrait of it.
- The camera height and tilt angle can be adjusted between tests with a tool, in minutes.
- The BLE antenna is close to the tag of a hen standing inside, and farther from the hens
  standing outside.
- Survives weeks in a covered run: dust, humidity, ammonia, 42 degC in shade.

Non-goals (v1):
- PIR. Owner decision: in v1 only BLE triggers. The case has no PIR place.
- Battery, solar panel, deep sleep (the firmware design assumes mains power).
- Outdoor rain protection. The box stands in a covered place.
- Foil shielding (firmware design section 5: only if the M2 measurement requires it).
- A fully printed corridor.

Anti-goals (failure even if it works technically):
- The hen does not enter, because the corridor is narrow, dark or scary.
- Two hens fit in at once, and the image or the identification gets mixed up.
- The window fogs up or gets dusty, and can only be cleaned by disassembly.
- A small change of the camera position requires reprinting the module.
- Metal (screw, aluminium tape) comes near the antenna.

## 3. Constraints and facts

- Printer: Bambu Lab P1S, 0.4 mm nozzle, build plate 256 x 256 mm. Material: PETG (PLA
  softens at 42 degC). According to the hen-tag-enclosure repo, the 0.16 mm layer profile
  worked well on this machine. The Bambu Studio CLI slicing check (`cad/slice_check.py`) can
  be read as a pattern.
- Electronics: Seeed XIAO ESP32S3 Sense. The board is 20.95 x 17.78 mm. The two boards
  together are 15 mm high (wiki). The USB-C sticks out 1.53 mm past the end of the board.
  The microSD is on top of the expansion board. In the model, the card sticks out about
  1 mm past the expansion board. Details and uncertain values: `DIMENSIONS.md` section 1.
- Camera: OV3660 (measured on our board, PID `0x3660`). Module 8 x 8 mm, lens D6.2 mm, total
  height 5.3 mm. Field of view: 85 deg horizontal, 102 deg diagonal. The cable is 21.2 mm long, so
  the camera can be at most about 2 cm from the board.
- Antenna: Seeed 2.4 GHz FPC ("2.4G A-02", the owner confirmed). Adhesive pad, 37.4 x 17.5 mm,
  at most 1.8 mm thick. The cable is 65 mm. So the distance between the antenna and the board
  is at most about 5-6 cm.
- Trigger and identification: BLE only. The tag is on the hen's back.
- Power: 5 V / 2 A outdoor USB power supply, USB-C cable. The same cable is used for flashing.
- Light: 5 V white LED strip (approx. 0.5 W) with a diffuser, around the camera window, so
  that it does not shine into the lens. Superseded by PR #4: lighting is external and not part
  of the case.
- Place: run, covered place. Dust, humidity, ammonia, 42 degC in shade.
- Hens: medium laying hybrids (approx. 2 kg, e.g. ISA Brown, Tetra).

## 4. Owner decisions (2026-11-05)

| Area | Decision |
|---|---|
| First case | Modular test bed; the final box after the tests |
| Corridor | Only the module and the fasteners are printed; the walls are plywood or OSB |
| Trigger | BLE only, no PIR place |
| Place | Run, covered place |
| Hen size | Medium laying hybrids: the corridor is approx. 25 cm wide, 40 cm high (inside dimensions) |
| Camera | Face-on, from behind the bowl; the image is a publishable portrait of the hen |
| Adjustment | Rail and tilt: the module slides up and down on the rail, the camera head can tilt |
| Bait bowl | Existing shop bowl, held by a printed holder in a fixed place |
| Antenna | Fixed under the roof, above the back, with a u.FL extension to the module |
| Exit | Dead end, the hen backs out |

## 5. Structure

### 5.1 Corridor (not printed)

- Plywood or OSB box: floor, two side walls, roof, front wall. The entrance is the open end,
  opposite the front wall.
- Inside dimensions approx. 25 cm wide, 40 cm high. One medium hen fits in. Two side by side
  do not.
- Owner decision: the corridor is a dead end. The hen backs out after eating. If the tests
  show that hens do not enter this way, an exit can be cut into the wood side wall later.
  The length is up to the implementer: the hen must stand fully inside while it bends to the
  bowl.
- The front wall has a window opening. Through it, the camera looks inward, over the bowl,
  toward the hen's head. The opening is large enough for the module to look in along its
  full rail travel.
- The inside of the corridor should be bright (not a closed, dark tunnel), so that the hen
  walks in. Open entrance, with a ventilation gap or a light roof if needed.
- At the fixing points, no metal within 10 cm of the antenna. Use wood or plastic screws,
  glue, or pegs there.

### 5.2 Electronics module (printed)

- Closed PETG box on the outer side of the front wall. Inside: the XIAO board, the LED strip
  driver (MOSFET, per the firmware design), the USB-C entry, one silica gel pocket. Superseded
  by PR #4: lighting is external, so the module has no LED strip, diffuser or MOSFET.
- **Camera head:** the front part of the module. It looks inward through the opening in the
  front wall. The camera sits in a tiltable head, with fixed positions, approx. every 15 deg,
  from horizontal downward. The camera cable is short (21.2 mm). So the XIAO board moves
  together with the head, or the head pivot is close to the board. The solution is up to the
  implementer, but the cable must not break and must not be under tension.
- **Window:** acrylic or PC sheet in front of the lens. It can be replaced and cleaned from
  outside, without tools or with one screw. The LED strip sits around the window, behind a
  diffuser. A rim separates it from the lens, so that no glare appears.
- **Antenna:** not in the module. It is on a separate holder under the roof (5.4a). A u.FL
  extension cable runs from the module to it, loosely, so that sliding and tilting of the
  module do not pull on it.
- **Power:** the USB-C cable enters from below, with a drip loop and strain relief. The plug
  does not load the board connector when pulled.
- **Service:** the microSD can be removed without opening the module, or by removing a cover.
  The cover screw does not go near the antenna.
- **Heat and dust:** ventilation with a labyrinth slot (against dust) at the top and bottom of
  the module. Light-coloured PETG. The silica gel pocket can be replaced without opening, or
  simply.

### 5.3 Rail (printed)

- Two vertical, split rails on the outer side of the front wall, screwed into the wood.
- The module slides up and down on the rail. It can be fixed at any height with a wing screw
  or a knob nut. The rail travel must cover the expected height of the hen's head while it
  eats, approx. 20 cm above the rim of the bowl.
- The tilt (5.2) and the height (5.3) together give the adjustment. The distance between the
  camera and the head is set by the bowl position (5.4).

### 5.4a Antenna holder (printed)

- Owner decision: the FPC antenna is fixed to the inner side of the roof, above the hen's
  back, because the tag is on the back. Moving the module does not move it. So the M2 BLE
  measurement is independent of the camera adjustment.
- The holder can be set forward and back under the roof, in fixed positions or with a slotted
  hole, so that the best place can be found during the measurement.
- Between the antenna and the module runs a 15-20 cm u.FL (IPEX) extension cable. This is a
  new part to purchase. The cable runs along the roof, guided by clips, out of the hen's reach.
- No metal within 10 cm of the antenna (5.1).

### 5.4 Bowl holder (printed)

- Ring or cradle that holds the existing shop bowl on the floor, in a fixed place, directly in
  front of the front wall. So the hen's head is always in the same place.
- The bowl diameter and height are parameters. The exact values must be measured with a
  calliper (section 7).
- The bowl can be removed for washing. The holder cannot.
- The placement of the holder (distance from the front wall) is up to the implementer. The
  goal: the distance between the camera and the hen's head falls in the 20-30 cm range of the
  firmware design, and the head fills the image. At an 85 deg horizontal field of view, the field
  of view is approx. 37 cm wide at 20 cm.

### 5.5 Designer decisions (the designer made them, the owner may override)

- **Landscape image.** The camera is in landscape orientation. The tilt axis is horizontal.
- **The whole module tilts, not only the camera.** The XIAO board, the camera and the USB-C
  plug sit in one body. That body is a carriage on the rail, and it tilts relative to the
  carriage. So the 21.2 mm camera cable does not move. The microSD and the plug also keep
  their fixed place inside the module. The USB-C cable runs loosely out of the module, in a
  loop, so that tilting and sliding do not pull on it.
- **LED driver (superseded by PR #4: lighting is external, no MOSFET in the case):** one AO3400 MOSFET on a small through-hole board (approx. 20 x 30 mm of space
  in the module), per the pin layout of the firmware design.
- **The bowl follows the 20-30 cm rule.** "Directly in front of the front wall" means the bowl
  is fixed in the strip in front of the front wall. The exact distance comes from the
  20-30 cm camera-head distance (approx. 15 cm from the wall).
- **The lens is behind the plane of the front wall,** so that the hen does not peck the window.

### 5.6 Outputs

- The Blender scene and the printable STL files (section 6).
- The Blender scene shows an 85 deg horizontal camera pyramid and a hen-head placeholder. It shows
  that, at the lower, middle and upper rail positions, the head is in the image. The owner does
  the physical test on the printed test bed.
- The wooden structure drawing: panel sizes, board thickness, the cut-out in the front wall,
  and the holes for the rail and the bowl holder.

## 6. Workflow (Blender MCP)

- The model is made in Blender, through the Blender MCP. Unit: mm (Scene Units: Metric,
  Unit Scale 0.001, Length: Millimeters).
- The parts (XIAO stack, camera, antenna, LED strip, USB-C plug) enter the scene as simplified
  placeholder bodies, with the sizes from `DIMENSIONS.md`, so that the fit can be checked. The
  Seeed STEP models can be converted to STL and imported. But the contents of
  `hardware/case/ref/` do not go into the repo (licence).
- Source and output: `hardware/case/station-case.blend`, one STL per printable part, for example
  `module-body.stl`, `module-lid.stl`, `camera-head.stl`, `rail.stl`, `bowl-holder.stl`,
  `window-frame.stl`. The names are up to the implementer.
- Every printable part fits on the 256 x 256 mm build plate. Each prints without supports, or
  with minimal supports.
- Fit tolerance: for the sliding and snap-fit parts, a test coupon is printed first, before the
  whole module (per the practice of the hen-tag-enclosure repo).
- Check: Bambu Studio CLI slicing without errors and without warnings.

## 7. Measure before printing (calliper)

Some values in `DIMENSIONS.md` come from a model or from a third party. They must be measured
on the real part before the module is final:
1. The existing bowl: diameter, rim height, foot.
2. The real height of the XIAO stack (wiki: 15 mm, model: 13.96 mm) and the board thickness.
3. How far the microSD sticks out of the expansion board, with a card inserted.
4. The head length and width of the USB-C plug, and the cable diameter.
5. The width and thickness of the LED strip, and the cutting pitch.
6. The real size of the antenna and the length of its cable.

## 8. Left to the implementer

- The corridor length and exact inside dimensions, the fit of the wood structure.
- The internal layout of the module, the mechanics of the tiltable head, the number of fixed
  positions.
- The rail length, the fixing method, the screw types (threaded insert, self-tapping).
- The LED strip length and placement, the diffuser material.
- The design of the ventilation, the labyrinth and the silica gel pocket.
- The module wall thickness and the print settings.

## 9. Done when

- Every STL slices without errors with the P1S profile, and prints in PETG.
- Assembled, the camera sees the head of a hen bending to the bowl at the lower, middle and
  upper rail positions. The head fills a large part of the image.
- The window can be cleaned in one minute, without disassembling the module.
- The M2 BLE measurement can be done on the test bed (inside / entrance / 1 m, 4 tags).
