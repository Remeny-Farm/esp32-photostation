"""Every dimension of the v1 case test bed, and the camera kinematics.

Pure Python (no bpy), so the numbers are unit-tested on the host (test_params.py)
and the Blender scripts import the same values.

Frames, all in millimetres:
  world   X across the corridor (0 = centre), Y along it (0 = inner face of the
          front wall, +Y towards the entrance), Z up (0 = top of the floor board).
  module  origin at the tilt pivot; x across, y forward (towards the wall), z up.
          World placement: rotate about X by -tilt (nose down), then translate to
          (0, pivot_y, pivot_z).

Values marked "measure" are placeholders until checked with calipers (spec section 7).
"""

import math
from dataclasses import dataclass, replace

Vec3 = tuple[float, float, float]

TILTS = (0, 15, 30, 45)
RAIL_PIVOT_Z = {"low": 125.0, "mid": 220.0, "high": 315.0}


@dataclass(frozen=True)
class P:
    # Printing
    bed: float = 250.0           # usable cube per part (P1S bed is 256)
    wall: float = 2.4            # 6 lines at 0.4
    clr: float = 0.3             # sliding fit, per side
    press: float = 0.1           # press fit, per side
    layer: float = 0.16

    # Corridor (plywood, not printed)
    t_wood: float = 12.0
    inner_w: float = 250.0
    inner_h: float = 400.0
    inner_len: float = 650.0
    open_w: float = 100.0        # front-wall opening, centred on X
    open_z0: float = 30.0
    open_z1: float = 355.0
    roof_hole_y: float = 10.0    # u.FL extension passes the roof here

    # Bowl and hen (measure)
    bowl_d_top: float = 180.0
    bowl_d_base: float = 150.0
    bowl_h: float = 60.0
    bowl_y: float = 185.0        # bowl centre from the inner wall face
    head_d: float = 50.0
    head_above_rim: float = 40.0

    # Camera optics (OV3660, DIMENSIONS.md section 2)
    hfov: float = 85.0
    aspect: float = 4 / 3

    # Module (local frame)
    pivot_y: float = -23.5       # world Y of the pivot axis
    mod_x: float = 32.0          # body spans x -mod_x .. +mod_x
    mod_y0: float = 2.0          # body front face
    mod_y1: float = -42.0        # body rear face (open, closed by the lid)
    mod_z0: float = -72.0        # body bottom
    mod_z1: float = 6.0          # body top
    lens: Vec3 = (0.0, 1.0, -20.0)   # lens front centre
    lens_bore_d: float = 6.6
    shroud_od: float = 10.0
    shroud_h: float = 2.0        # proud of the body front face
    led_x: float = 18.0          # LED pockets at x = +-led_x
    led_pocket: Vec3 = (9.0, 2.5, 26.0)  # x, depth (y), height (z)

    # Window frame (slides down into two guides on the body front)
    frame_w: float = 56.0
    frame_h: float = 40.0
    frame_d: float = 4.0
    frame_top_z: float = 4.0
    pane: Vec3 = (20.0, 2.0, 20.0)   # acrylic pane x, thickness, z
    diffuser_t: float = 0.48     # printed PETG skin over the LED windows
    guide_w: float = 3.0         # guide rail width beside the frame
    guide_lip: float = 1.5       # lip overlapping the frame edge

    # Electronics inside the module (local frame; DIMENSIONS.md section 1)
    board_w: float = 17.78
    board_len: float = 20.95
    board_back_y: float = -14.0  # main PCB bottom face
    board_z1: float = -12.0      # u.FL end (top)
    stack_h: float = 15.0
    usbc_overhang: float = 1.53
    usb_mould: Vec3 = (12.4, 6.5, 25.0)  # width, thickness, length (measure)
    usb_cable_d: float = 4.5     # measure
    usb_hole: tuple[float, float] = (13.5, 7.5)
    ufl_slot_w: float = 3.0
    cam_module: Vec3 = (8.0, 5.3, 8.0)
    perfboard: Vec3 = (20.0, 1.6, 30.0)
    perf_parts_h: float = 8.0
    led_strip: Vec3 = (8.0, 2.0, 25.0)
    silica: Vec3 = (30.0, 10.0, 20.0)
    sled_t: float = 2.0
    sled_rib_y: tuple[float, float] = (-13.8, -16.2)
    sled_z: tuple[float, float] = (-8.0, -34.0)

    # Fasteners
    pivot_pilot_d: float = 3.5   # M4 self-tapping into PETG
    pivot_clear_d: float = 4.3
    index_r: float = 16.0
    index_pilot_d: float = 2.6   # M3 self-tapping into PETG
    index_clear_d: float = 3.3
    lid_screw_pilot_d: float = 2.6
    lid_screw_clear_d: float = 3.3

    # Rails (world frame, +X rail; the other is mirrored)
    rail_x: float = 56.0
    rail_w: float = 24.0
    rail_d: float = 9.0          # Y -t_wood .. -t_wood - rail_d
    channel_w: float = 8.4       # holds the M5 hex head flats
    channel_d: float = 4.5
    slot_w: float = 5.5
    bolt_d: float = 5.0
    bolt_dz: float = -40.0       # bolt Z relative to the pivot
    slot_z0: float = 81.5
    slot_z1: float = 278.5
    rail_foot: float = 26.0
    wood_screw_d: float = 4.5
    tick_pitch: float = 10.0

    # Carriage (module local frame)
    carr_y: tuple[float, float] = (2.5, -3.5)     # plate, back face on the rail front
    carr_x: float = 68.0
    carr_z: tuple[float, float] = (-84.0, 16.0)
    cheek_x: tuple[float, float] = (33.0, 39.0)
    cheek_y: tuple[float, float] = (6.5, -20.5)
    cheek_z: tuple[float, float] = (-8.0, 18.0)
    tongue: tuple[float, float] = (5.0, 2.0)       # width, height into the slot
    tongue_len: float = 60.0

    # Bowl holder
    ring_wall: float = 4.0
    ring_h: float = 20.0
    ring_tabs: int = 3

    # Antenna holder (world frame) and the FPC radiator (DIMENSIONS.md section 3)
    antenna_y: float = 300.0
    antenna_fpc: Vec3 = (17.5, 37.4, 1.8)  # x, y, z
    ant_plate: Vec3 = (50.0, 130.0, 4.0)
    ant_pocket_depth: float = 1.2
    ant_slot: tuple[float, float] = (4.5, 100.0)
    clip: Vec3 = (12.0, 20.0, 6.0)
    coax_d: float = 1.13
    metal_keepout: float = 100.0

    def with_(self, **kw) -> "P":
        return replace(self, **kw)


def _rot(pt: Vec3, tilt: float) -> Vec3:
    a = math.radians(tilt)
    x, y, z = pt
    return (x, y * math.cos(a) + z * math.sin(a), -y * math.sin(a) + z * math.cos(a))


def local_to_world(p: P, pt: Vec3, pivot_z: float, tilt: float) -> Vec3:
    x, y, z = _rot(pt, tilt)
    return (x, y + p.pivot_y, z + pivot_z)


def lens_pose(p: P, pivot_z: float, tilt: float) -> tuple[Vec3, Vec3]:
    return local_to_world(p, p.lens, pivot_z, tilt), _rot((0.0, 1.0, 0.0), tilt)


def head_center(p: P) -> Vec3:
    return (0.0, p.bowl_y, p.bowl_h + p.head_above_rim)


def aim_tilt(p: P, pivot_z: float) -> float:
    # Small-angle fixed point: the lens moves a little as the module tilts.
    t = 0.0
    for _ in range(5):
        lens, _ = lens_pose(p, pivot_z, t)
        h = head_center(p)
        t = math.degrees(math.atan2(lens[2] - h[2], h[1] - lens[1]))
    return t


def nearest_tilt(angle: float) -> int:
    return min(TILTS, key=lambda t: abs(t - angle))


def vfov_deg(p: P) -> float:
    return 2 * math.degrees(math.atan(math.tan(math.radians(p.hfov / 2)) / p.aspect))


def head_in_fov(p: P, pivot_z: float, tilt: float) -> bool:
    lens, fwd = lens_pose(p, pivot_z, tilt)
    up = _rot((0.0, 0.0, 1.0), tilt)
    d = tuple(h - l for h, l in zip(head_center(p), lens))
    along = sum(a * b for a, b in zip(d, fwd))
    if along <= 0:
        return False
    margin = math.degrees(math.asin(p.head_d / 2 / math.dist(head_center(p), lens)))
    h_ang = abs(math.degrees(math.atan2(d[0], along)))
    v_ang = abs(math.degrees(math.atan2(sum(a * b for a, b in zip(d, up)), along)))
    return h_ang + margin <= p.hfov / 2 and v_ang + margin <= vfov_deg(p) / 2


def antenna_cable_mm(p: P, pivot_z: float) -> float:
    """u.FL route: module top, up outside the front wall, over the roof to the roof
    hole, through the roof, along its underside to the antenna, plus 50 mm slack."""
    _, exit_y, exit_z = local_to_world(p, (0.0, p.board_back_y + 2, p.mod_z1), pivot_z, 0)
    roof_top = p.inner_h + p.t_wood
    return ((roof_top - exit_z) + (p.roof_hole_y - exit_y) + p.t_wood
            + (p.antenna_y - p.roof_hole_y) + 50.0)


def rail_length(p: P) -> float:
    return (p.slot_z1 - p.slot_z0) + 2 * p.rail_foot
