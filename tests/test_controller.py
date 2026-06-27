import math
import unittest

from controller import build_controller_message, quaternion_to_controller_axes
from server import build_broadcast_messages


class ControllerMappingTest(unittest.TestCase):
    def test_identity_quaternion_maps_to_centered_axes(self):
        axes = quaternion_to_controller_axes({"x": 0, "y": 0, "z": 0, "w": 1})

        self.assertEqual(axes, {"yaw": 0.0, "pitch": 0.0, "roll": 0.0})

    def test_positive_pitch_maps_to_full_positive_axis(self):
        q = {
            "x": math.sin(math.pi / 4),
            "y": 0,
            "z": 0,
            "w": math.cos(math.pi / 4),
        }

        axes = quaternion_to_controller_axes(q)

        self.assertEqual(axes["pitch"], 1.0)
        self.assertEqual(axes["yaw"], 0.0)
        self.assertEqual(axes["roll"], 0.0)

    def test_controller_message_keeps_raw_quaternion_for_consumers(self):
        q = {"x": 0, "y": 0, "z": 0, "w": 1}

        message = build_controller_message(q)

        self.assertEqual(message["type"], "controller")
        self.assertEqual(message["axes"], {"yaw": 0.0, "pitch": 0.0, "roll": 0.0})
        self.assertEqual(message["quaternion"], q)


class ServerBroadcastMessagesTest(unittest.TestCase):
    def test_orientation_payload_broadcasts_orientation_and_controller_messages(self):
        orientation = {
            "type": "orientation",
            "quaternion": {"x": 0, "y": 0, "z": 0, "w": 1},
        }

        messages = build_broadcast_messages(orientation)

        self.assertEqual(messages[0], orientation)
        self.assertEqual(messages[1]["type"], "controller")
        self.assertEqual(messages[1]["axes"], {"yaw": 0.0, "pitch": 0.0, "roll": 0.0})

    def test_non_orientation_payload_broadcasts_unchanged(self):
        disconnected = {"type": "disconnected"}

        self.assertEqual(build_broadcast_messages(disconnected), [disconnected])


if __name__ == "__main__":
    unittest.main()
