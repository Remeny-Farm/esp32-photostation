"""Host tests for the test-bed geometry: no Blender needed.

Run: cd hardware/case/cad && python3 -m unittest test_params -v
"""

import math
import unittest

from params import (P, RAIL_PIVOT_Z, TILTS, aim_tilt, antenna_cable_mm, head_in_fov,
                    head_center, lens_pose, nearest_tilt, rail_length, vfov_deg)

p = P()


def dist(a, b):
    return math.dist(a, b)


class Kinematics(unittest.TestCase):
    def test_low_lens_is_level_with_head(self):
        _, view = lens_pose(p, RAIL_PIVOT_Z["low"], 0)
        self.assertAlmostEqual(view[0], 0.0)
        self.assertAlmostEqual(view[1], 1.0)
        self.assertAlmostEqual(view[2], 0.0)

    def test_tilt_points_down(self):
        _, view = lens_pose(p, RAIL_PIVOT_Z["high"], 45)
        self.assertAlmostEqual(view[1], math.cos(math.radians(45)))
        self.assertAlmostEqual(view[2], -math.sin(math.radians(45)))

    def test_nearest_tilt(self):
        self.assertEqual(nearest_tilt(-3.0), 0)
        self.assertEqual(nearest_tilt(26.6), 30)
        self.assertEqual(nearest_tilt(80.0), 45)

    def test_distance_in_range(self):
        # Firmware design: the camera is 20-30 cm from the head.
        for state, z in RAIL_PIVOT_Z.items():
            lens, _ = lens_pose(p, z, nearest_tilt(aim_tilt(p, z)))
            d = dist(lens, head_center(p))
            self.assertTrue(200 <= d <= 300, f"{state}: {d:.0f} mm")

    def test_head_in_fov_all_states(self):
        for state, z in RAIL_PIVOT_Z.items():
            self.assertTrue(head_in_fov(p, z, nearest_tilt(aim_tilt(p, z))), state)

    def test_lens_behind_wall(self):
        # The lens stays behind the outer wall face with a 3 mm standoff, so a hen
        # cannot peck the window.
        for z in RAIL_PIVOT_Z.values():
            for t in TILTS:
                lens, _ = lens_pose(p, z, t)
                self.assertLessEqual(lens[1], -p.t_wood - 3, (z, t))

    def test_vfov(self):
        self.assertTrue(68.5 < vfov_deg(p) < 69.5, vfov_deg(p))


class Fit(unittest.TestCase):
    def test_rail_fits_bed(self):
        self.assertLessEqual(rail_length(p), 250)

    def test_rail_slot_covers_travel(self):
        lo = min(RAIL_PIVOT_Z.values()) + p.bolt_dz - p.bolt_d / 2
        hi = max(RAIL_PIVOT_Z.values()) + p.bolt_dz + p.bolt_d / 2
        self.assertLessEqual(p.slot_z0, lo)
        self.assertGreaterEqual(p.slot_z1, hi)
        # The tongue (tongue_len around the bolt) stays in the slot too. Its square corners
        # sit at half the tongue width (carriage: slot_w - 2 clr) inside the rounded ends.
        r, w = p.slot_w / 2, (p.slot_w - 2 * p.clr) / 2
        end = r - math.sqrt(r * r - w * w)
        for state in ("low", "high"):
            bolt = RAIL_PIVOT_Z[state] + p.bolt_dz
            self.assertGreaterEqual(bolt - p.tongue_len / 2, p.slot_z0 + end, state)
            self.assertLessEqual(bolt + p.tongue_len / 2, p.slot_z1 - end, state)

    def test_bevel_leaves_wood_beside_rail_screws(self):
        # At the inner face the bevelled opening reaches open_w / 2 + open_bevel; the rail
        # screw holes (D wood_screw_d at x = +-rail_x) need 5 mm of plywood beside it.
        wood = p.rail_x - p.wood_screw_d / 2 - (p.open_w / 2 + p.open_bevel)
        self.assertGreaterEqual(wood, 5.0)

    def test_antenna_cable_reported(self):
        # The spec assumed a 15-20 cm u.FL extension; the real route is longer.
        # This pins the computed figure the README's parts list quotes.
        worst = max(antenna_cable_mm(p, z) for z in RAIL_PIVOT_Z.values())
        self.assertGreater(worst, 200)
        self.assertLess(worst, 800)


if __name__ == "__main__":
    unittest.main()
