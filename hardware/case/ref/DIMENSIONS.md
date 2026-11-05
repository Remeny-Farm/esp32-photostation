# Mechanical reference data for the hen photo station enclosure

Collected 2026-11-05. All dimensions in mm. Downloaded files are untrusted data and were only read, never executed.

Status key: **OFFICIAL** = manufacturer/standards body drawing or model. **3RD-PARTY** = retailer or other third-party figure. **ESTIMATED** = derived by me, not measured on a part. **MODEL** = read from the official 3D model (geometry, not a dimensioned drawing).

Coordinate frame for the XIAO STEP model (as shipped): X = board length (u.FL end at low X, USB-C end at high X), Y = stack height (up = camera side), Z = board width. Values below are given relative to the main-board corner (low X, low Z, Y = main PCB top surface = 0) unless stated otherwise.

## 1. Seeed Studio XIAO ESP32S3 Sense (main board + Sense expansion board)

Files: `xiao_esp32s3_sense/` (zips contain STEP + photos; DXF are PCB-layout style drawings, mostly pad/silk data).

| Item | Value | Status | Source |
|---|---|---|---|
| Main PCB outline | 20.95 x 17.78 (nominal "21 x 17.8") | OFFICIAL (model) + wiki text | wiki 21 x 17.8: https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/ ; model: https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-sense-3d_model.zip |
| Main PCB thickness | 1.25 in model (slab spans Y -0.25 to +1.00). Wiki gives no board thickness. | MODEL (verify with calipers; real PCB may be 1.0-1.2) | same zip |
| Main PCB corner | 45 deg chamfers at the USB-C end corners (visible in the dimensioning DXF); chamfer size not read | OFFICIAL (DXF) | https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/XIAO_ESP32S3_v1.1_Dimensioning.dxf |
| Castellated/edge pads | Half-moon pads on both long edges, 7 per side + extra pads, pitch 2.54 (0.1 in; DXF grid is on 2.54/0.635 multiples) | OFFICIAL (DXF, pitch inferred from geometry + XIAO form factor); pad length not extracted | same DXF |
| RF shield on main board | 10.6 (X) x 12.6 (Z), top at Y 3.00, i.e. 2.0 above PCB top | MODEL | zip above |
| USB-C receptacle | Body 7.30 (X) x 8.94 (Z) x 4.20 (Y: 0.01..4.21), i.e. 3.21 above the PCB top surface; centred on board width (Z centre -6.12 vs board centre -6.11); overhangs the board end by 1.53 | MODEL | zip above |
| u.FL connector (U.FL-R-SMT-1) | Footprint 3.00 x 3.10, height 1.25 above PCB top (Y 1.00..2.25). Position: X 0.22..3.22 from the u.FL end of the board, Z 2.61..5.71 from the low-Z long edge (near one corner, end opposite the USB-C). Wiki: "bottom left of front side" | MODEL; wiki text | zip above; wiki |
| B2B connector on main board (DF40C-30DP-0.4V) | 2.97 x 7.52, height 1.14 above PCB top; X 0.26..3.23 from u.FL end, Z 7.28..14.80 from low-Z edge | MODEL | zip above |
| Sense expansion board B2B (DF40HC(3.0)-30DS) | Mated height 2.90 (Y 1.03..3.93). Expansion PCB underside is 2.93 above main PCB top. | MODEL | zip above |
| Sense expansion PCB | 14.68 x 16.78 x 1.25 thick (Y 3.93..5.18). Starts 0.30 beyond the u.FL end of main PCB, ends 6.58 short of the USB-C end of the main PCB, so the USB-C end of the main board is uncovered. Z: 0.50 in from low-Z edge, 0.50 in from high-Z edge | MODEL | zip above |
| Camera FPC connector (JUSHUO AFC01-S24FCA-00, 24-pin) | 6.00 (X) x 16.20 (Z) x 2.01 high (Y 5.17..7.18) on the expansion board top | MODEL | zip above |
| microSD slot (Amphenol 10067099-200LF as named in model) | Body 5.50 (X) x 11.40 (Z) x 2.65 (Y 5.13..7.78) on the expansion board top. Card insertion axis is +X (towards USB-C end) | MODEL | zip above |
| microSD card as modelled (seated) | Occupies X 0.33..15.39 (i.e. 9.7 beyond the expansion PCB end), Y 6.60..8.25, Z width 11.18. Card therefore lies over the main board near USB-C. Model slot depth looks simplified: verify on the real part | MODEL (unverified) | zip above |
| Digital mic (MIC on expansion board) | footprint about 4 x 3 near the u.FL-side corner of the expansion board's top (from ExpBoard DXF, not dimensioned) | OFFICIAL (DXF, rough) | https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/XIAO_ESP32S3_ExpBoard_v1.0_top.dxf |
| Camera module in model | 8.00 x 8.00 module, Y 7.95..13.71 (5.76 tall incl. lens), centre at X 8.75/Z -6.75 in model frame, i.e. over the USB-C end of the main board. Lens parts: 1.5 x 1.5 core on a 3.56 stalk. FPC drawn as a bent 7.0 x 6.0 (Y 5.60..8.50) section plus 5.0 x 12.5 tail | MODEL (generic placeholder camera) | zip above |
| Total stack height | Y -0.25 .. 13.71 = 13.96 in model (main PCB bottom to lens top). Wiki states 15 (21 x 17.8 x 15 mm with expansion board). Use 15.0 as design value | wiki OFFICIAL; model MODEL | https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/ |
| Main PCB length incl. USB-C overhang | 20.95 + 1.53 = 22.48 | derived from MODEL | zip above |
| Seeed's own 2-part housing (STEP) | Outer 22.18 x 25.32; top shell height 9.03, bottom shell height 5.40 (assembled height <= 14.43 if no overlap) | OFFICIAL (Seeed) | https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/XIAO-ESP32S3-Sense-housing-design(top).stp (and `(bottom).stp`) |
| Plain XIAO ESP32S3 model (no Sense) | `seeed-studio-xiao-esp32s3-3d_model.zip`: same main-board geometry | OFFICIAL | https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-3d_model.zip |

Notes:
- The Seeed wiki says new Sense units ship with the OV5640 (auto-focus, larger module); during the transition boards may carry OV5640 or OV3660. Check which camera you actually hold. The OV5640 module drawing is in `ov3660/OV5640_Camera_Module_Specification.pdf`.
- STEP bounding boxes were computed from the official STEP assembly (OCC, world coordinates). They are not dimensions printed on a drawing.

## 2. Camera module OV3660 (24-pin FPC, as shipped with XIAO Sense)

Files: `ov3660/OV3660_Camera_Module_Specification.pdf`, `ov3660/OV5640_Camera_Module_Specification.pdf`.

| Item | Value | Status | Source |
|---|---|---|---|
| Module PCB | 8.00 x 8.00 (hole pattern 6.50 x 6.50 on the back) | OFFICIAL (module vendor drawing hosted by Seeed) | https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/new-res/OV3660_Camera_Module_Specification.pdf |
| Lens barrel diameter | 6.20 (round, outer) | OFFICIAL | same |
| Total height (lens front to rear face) | 5.30 overall; drawing also shows 5.00, 2.70 (barrel stand-out) and 1.55 (rear/PCB stack). Exact meaning of 5.00 not labelled | OFFICIAL (ambiguity noted) | same |
| FPC | Width 6.50, total length 21.20 from module edge to end of the stiffener, thickness 0.30 on contact end | OFFICIAL | same |
| FPC contact tail | 12.50 wide x 4.00 long stiffened area, contact 24 pins, pitch visible dimension 0.20/0.30 + 5.04 span (i.e. 0.5 mm pitch class) | OFFICIAL | same |
| Lens: EFL / aperture | 1.63 mm +-5% / F2.2, 5P + 650 nm IR | OFFICIAL | same |
| Field of view | Diagonal 102 deg, horizontal 85 deg (drawing also shows an angle of 103 deg) | OFFICIAL | same |
| Sensor | OV3660 1/5", 2048 x 1536 | OFFICIAL | same |
| OV5640 module (current Sense option) | 8.50 x 8.50 module, lens/body height 5.2-5.7 (5.2 +-0.2 / 5.7 +-0.2 read from drawing), FPC 70.5 +-0.2 long as drawn in the vendor sheet, FOV 69 deg, EFL 3.29, auto-focus | OFFICIAL (read from a low-resolution drawing; verify) | https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/new-res/OV5640_Camera_Module_Specification.pdf |

## 3. Antenna shipped with XIAO ESP32S3

Files: `antenna/Datasheet_2.4GHz_FPC_Antenna_1.16dbi_for_XIAO_ESP32S3.pdf`.

The wiki says "take out the antenna inside the package" without naming the model. The Seeed datasheet below is for the FPC antenna Seeed sells for this board; the Pi Hut lists 1x antenna in the XIAO ESP32S3 box. Owner confirmed 2026-11-05: the box holds this FPC antenna (marked "2.4G A-02", self-adhesive radiator with release paper on the end of the cable).

| Item | Value | Status | Source |
|---|---|---|---|
| FPC antenna radiator (self-adhesive) | 37.4 +-0.2 x 17.5 +-0.2; solder-joint/total height <= 1.80 incl. release paper | OFFICIAL | https://files.seeedstudio.com/wiki/XIAO_WiFi/antenna/FPC_Antenna_2.4GHz_1.16dbi_for_XIAO_ESP32S3/res/Datasheet_2.4GHz_FPC_Antenna_1.16dbi_for_XIAO_ESP32S3.pdf |
| Cable | coax diameter 1.13 +-0.1, length 65.0 +-2.0, I-PEX/u.FL type connector | OFFICIAL | same |
| Gain / VSWR | 1.16 dBi peak, VSWR 3.67 @ 2.4 GHz | OFFICIAL | same |
| Rod antenna (alternative, sold separately) | 13 diameter x 134, SMA-to-I-PEX adapter cable (120 listed for a separately sold cable; length in the kit not stated) | 3RD-PARTY (retailer) | https://core-electronics.com.au/24ghz-rod-antenna-for-xiao-esp32c3.html.md |

## 4. AM312 mini PIR

Files: `am312/pir_am312_datasheet.pdf` (bare sensor manual by the maker, Nanyang Senba).

| Item | Value | Status | Source |
|---|---|---|---|
| Sensor can (TO-5 style, bare AM312 element) | diameter 9.1 +-0.1 body, 8.2 +-0.2 window, height 4.2 +-0.2, leads 13.5 +-1 long, 0.45 diameter, lead span 5.08 +-0.2 (pins: 1 VDD, 2 REL/OUT, 3 VSS) | OFFICIAL | https://ocw.cs.pub.ro/courses/_media/pm/prj2023/ncaroi/pir_am312_datasheet.pdf (copy of Senba manual; original site www.nysenba.com) |
| Module PCB (typical breakout) | 10 x 8 | 3RD-PARTY (retailer) | https://probots.co.in/am312-mini-pir-motion-sensor-module.html |
| Module overall incl. dome | roughly 12 x 25 (other listings say 15 x 25); not consistent | 3RD-PARTY | search result summaries (Makers Electronics, RAK listing) |
| Dome lens diameter | 10 | 3RD-PARTY | probots page above |
| Detection angle / range | <= 100 deg cone, about 3-5 m | 3RD-PARTY | probots page above |
| Pin header | 3 pins (VCC, OUT, GND); pitch not stated in any source | NOT FOUND (assume 2.54, ESTIMATED) | probots page |
| Dome lens height | not found | NOT FOUND | - |

## 5. 5 V white LED strip (generic SMD2835/5050)

Files: `led_strip/` (two third-party 2835 strip datasheets, not for the exact strip you buy).

| Item | Value | Status | Source |
|---|---|---|---|
| 8 mm 5 V 2835 strip: width, density | 8 FPC width, 120 LEDs/m, single-LED cuts | 3RD-PARTY | https://dekingled.com/en/m/product/detail/12v-24v-smd-led-strip/smd-led-strip-5v-102.html |
| LED pitch for 120 LEDs/m | 8.33 (computed 1000/120) | ESTIMATED | derived |
| Cut pitch for 5 V strips | per LED (about 8.33 at 120/m) or per 3 LEDs (25 mm) for 12 V strips; for a 60 LEDs/m 8 mm strip the cut unit is 50 mm | 3RD-PARTY | https://grobotronics.com/led-strip-2835-ip20-60l-m-8mm-warm-white-5m.html ; `led_strip/YJWJ025-1.3_YJ-VTC-RB-2835-12V-G01.pdf` (10 mm wide, cut every 3 LEDs = 25 mm) |
| Total strip thickness incl. LED and tape | 2 (5 mm 2835 strip "5000x5x2 mm") | 3RD-PARTY | `led_strip/2835smd-120leds-5mm-RGB-specification-1.pdf` (https://www.ledyilighting.com/wp-content/uploads/2021/10/2835smd-120leds-5mm-RGB-specification-1.pdf) |
| 5050 chip strip | not researched; 5050 package is 5.0 x 5.0 x about 1.6 plus FPC about 0.2 and tape about 0.3-0.5 | ESTIMATED (my general knowledge) | - |

## 6. microSD card

| Item | Value | Status | Source |
|---|---|---|---|
| Card size | 15 x 11 x 1.0 (L x W x T) | 3RD-PARTY (secondary; matches SD Association form factor) | https://en.wikipedia.org/wiki/SD_card |
| Insertion clearance | Slide-in along the 15 mm axis. Model shows the card seated with 9.7 mm sticking out past the expansion board toward the USB-C end. Leave >= 16 mm free length in the insertion direction plus >= 1.5 mm above the card, if the card must be swapped without opening the case. A fixed card needs none | ESTIMATED from the Seeed model | `xiao_esp32s3_sense/seeed-studio-xiao-esp32s3-sense-3d_model.zip` |
| Slot connector datasheet (Amphenol 10067099-200LF) | not downloaded (server returned 403) | NOT FOUND | https://cdn.amphenol-cs.com/media/wysiwyg/files/documentation/datasheet/boardwiretoboard/bwb_sdmemorycard.pdf |

## 7. USB-C cable plug overmould (5 V USB 2.0 cable)

Files: `usbc_plug/USB_Type-C_Compliance_Document_rev_1_2.pdf` (USB-IF).

| Item | Value | Status | Source |
|---|---|---|---|
| Overmould width | <= 12.35 | OFFICIAL (USB-IF) | https://www.usb.org/sites/default/files/USB_Type-C_Compliance_Document_rev_1_2.pdf (table, dimension 1) |
| Overmould height | <= 6.5 | OFFICIAL (USB-IF) | same (dimension 14) |
| Metal plug | width 8.25 +-0.03, thickness 2.40 +-0.03, length 6.65 +-0.10 | OFFICIAL (USB-IF) | same |
| Overmould length (along cable) | not specified in the USB-IF document; typical cables 20-30 (ESTIMATED), one DigiKey forum poster gives 12.5 for a recessed port (3RD-PARTY, not a spec) | NOT FOUND | https://forum.digikey.com/t/overmold-size-of-the-usb-c-male-end/70874 |
| Cable diameter | not researched; typical USB 2.0 2-core/4-core cable 3.0-4.5 | ESTIMATED | - |
| Note | A single GitHub PR claims a newer envelope of 12.85 x 7.0; not confirmed in any USB-IF document I opened | UNVERIFIED | https://github.com/crimpdeq/crimpdeq-case/pull/7 |

## What I could NOT find

- Printed dimension values on Seeed's DXFs (text is stroked into polylines; I only used them for pad pitch and outline shape). No official PDF dimension drawing exists on the wiki; the board STEP is the authority.
- Real main-board PCB thickness (model slab is 1.25 mm; wiki silent).
- AM312 dome height and pin pitch; module drawings.
- Exact 5 V strip's thickness/pitch (only generic 2835 strips found; 5050 not researched).
- USB-C overmould length, cable OD.
- microSD slot connector drawing (Amphenol, 403) and whether the real card sticks out as in the model.
- OV3660 5.00 dimension meaning and OV5640 module total height precisely (low-res drawing).
- No unofficial (GrabCAD/Printables) models were used; official ones exist.
