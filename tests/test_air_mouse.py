import ctypes
import math
import unittest
from unittest.mock import patch

from air_mouse import (
    AirMouseMapper,
    AirMouseSettings,
    CGPoint,
    MacMouseController,
    StableNeutralCalibrator,
    quaternion_from_euler,
)


class AirMouseMapperTest(unittest.TestCase):
    def test_identity_pose_produces_zero_movement_after_calibration(self):
        mapper = AirMouseMapper(AirMouseSettings())
        q = {"x": 0, "y": 0, "z": 0, "w": 1}

        mapper.set_neutral(q)

        self.assertEqual(mapper.pointer_delta(q), (0.0, 0.0))

    def test_current_neutral_pose_produces_zero_movement(self):
        mapper = AirMouseMapper(AirMouseSettings())
        q = quaternion_from_euler(yaw=0.35, pitch=-0.22, roll=0.1)

        mapper.set_neutral(q)

        self.assertEqual(mapper.pointer_delta(q), (0.0, 0.0))

    def test_positive_yaw_maps_to_negative_horizontal_movement(self):
        mapper = AirMouseMapper(AirMouseSettings(sensitivity=100, deadzone=0))
        mapper.set_neutral({"x": 0, "y": 0, "z": 0, "w": 1})

        dx, dy = mapper.pointer_delta(quaternion_from_euler(yaw=0.2, pitch=0, roll=0))

        self.assertLess(dx, 0)
        self.assertEqual(dy, 0.0)

    def test_positive_pitch_maps_to_negative_vertical_movement(self):
        mapper = AirMouseMapper(AirMouseSettings(sensitivity=100, deadzone=0))
        mapper.set_neutral({"x": 0, "y": 0, "z": 0, "w": 1})

        dx, dy = mapper.pointer_delta(quaternion_from_euler(yaw=0, pitch=0.2, roll=0))

        self.assertEqual(dx, 0.0)
        self.assertLess(dy, 0)

    def test_deadzone_suppresses_small_jitter(self):
        mapper = AirMouseMapper(AirMouseSettings(sensitivity=100, deadzone=0.05))
        mapper.set_neutral({"x": 0, "y": 0, "z": 0, "w": 1})

        delta = mapper.pointer_delta(quaternion_from_euler(yaw=0.03, pitch=-0.03, roll=0))

        self.assertEqual(delta, (0.0, 0.0))

    def test_max_speed_clamps_large_movement(self):
        mapper = AirMouseMapper(AirMouseSettings(sensitivity=1000, deadzone=0, max_speed=12))
        mapper.set_neutral({"x": 0, "y": 0, "z": 0, "w": 1})

        dx, dy = mapper.pointer_delta(
            quaternion_from_euler(yaw=math.pi / 2, pitch=math.pi / 2, roll=0)
        )

        self.assertLessEqual(math.hypot(dx, dy), 12.0001)

    def test_smoothing_blends_toward_target_movement(self):
        mapper = AirMouseMapper(AirMouseSettings(sensitivity=100, deadzone=0, smoothing=0.5))
        mapper.set_neutral({"x": 0, "y": 0, "z": 0, "w": 1})

        dx, dy = mapper.pointer_delta(quaternion_from_euler(yaw=0.2, pitch=0, roll=0))

        self.assertAlmostEqual(dx, -10.0, places=4)
        self.assertEqual(dy, 0.0)


class StableNeutralCalibratorTest(unittest.TestCase):
    def test_captures_first_pose_after_required_stable_samples(self):
        calibrator = StableNeutralCalibrator(required_samples=3, max_angle_delta=0.02)
        q = quaternion_from_euler(yaw=0.1, pitch=0.1, roll=0)

        self.assertIsNone(calibrator.observe(q))
        self.assertIsNone(calibrator.observe(quaternion_from_euler(yaw=0.105, pitch=0.1, roll=0)))
        neutral = calibrator.observe(quaternion_from_euler(yaw=0.108, pitch=0.1, roll=0))

        self.assertIsNotNone(neutral)

    def test_unstable_pose_resets_stable_sample_count(self):
        calibrator = StableNeutralCalibrator(required_samples=3, max_angle_delta=0.02)

        self.assertIsNone(calibrator.observe(quaternion_from_euler(yaw=0.1, pitch=0, roll=0)))
        self.assertIsNone(calibrator.observe(quaternion_from_euler(yaw=0.5, pitch=0, roll=0)))
        self.assertIsNone(calibrator.observe(quaternion_from_euler(yaw=0.505, pitch=0, roll=0)))
        neutral = calibrator.observe(quaternion_from_euler(yaw=0.508, pitch=0, roll=0))

        self.assertIsNotNone(neutral)


class FakeFunction:
    def __init__(self, result=None):
        self.result = result
        self.argtypes = None
        self.restype = None
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class FakeApplicationServices:
    def __init__(self):
        self.CGEventCreate = FakeFunction(result=123456789123)
        self.CGEventGetLocation = FakeFunction(result=CGPoint(10, 20))
        self.CGWarpMouseCursorPosition = FakeFunction()
        self.CGAssociateMouseAndMouseCursorPosition = FakeFunction()
        self.CFRelease = FakeFunction()


class MacMouseControllerTest(unittest.TestCase):
    def test_declares_core_graphics_pointer_argument_types(self):
        fake_cg = FakeApplicationServices()

        with patch("air_mouse.platform.system", return_value="Darwin"):
            with patch("air_mouse.ctypes.cdll.LoadLibrary", return_value=fake_cg):
                MacMouseController()

        self.assertEqual(fake_cg.CGEventCreate.argtypes, [ctypes.c_void_p])
        self.assertEqual(fake_cg.CGEventGetLocation.argtypes, [ctypes.c_void_p])
        self.assertEqual(fake_cg.CFRelease.argtypes, [ctypes.c_void_p])


if __name__ == "__main__":
    unittest.main()
