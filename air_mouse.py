#!/usr/bin/env python3
import argparse
import asyncio
import ctypes
import json
import logging
import math
import platform
from dataclasses import dataclass

import websockets

from controller import quaternion_to_euler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

IDENTITY = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def normalize_quaternion(q):
    length = math.hypot(q["x"], q["y"], q["z"], q["w"])
    if not length:
        return dict(IDENTITY)

    return {
        "x": q["x"] / length,
        "y": q["y"] / length,
        "z": q["z"] / length,
        "w": q["w"] / length,
    }


def inverse_quaternion(q):
    normalized = normalize_quaternion(q)
    return {
        "x": -normalized["x"],
        "y": -normalized["y"],
        "z": -normalized["z"],
        "w": normalized["w"],
    }


def multiply_quaternions(a, b):
    return normalize_quaternion(
        {
            "x": a["w"] * b["x"] + a["x"] * b["w"] + a["y"] * b["z"] - a["z"] * b["y"],
            "y": a["w"] * b["y"] - a["x"] * b["z"] + a["y"] * b["w"] + a["z"] * b["x"],
            "z": a["w"] * b["z"] + a["x"] * b["y"] - a["y"] * b["x"] + a["z"] * b["w"],
            "w": a["w"] * b["w"] - a["x"] * b["x"] - a["y"] * b["y"] - a["z"] * b["z"],
        }
    )


def quaternion_from_euler(yaw=0.0, pitch=0.0, roll=0.0):
    yaw_q = {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)}
    pitch_q = {"x": math.sin(pitch / 2), "y": 0.0, "z": 0.0, "w": math.cos(pitch / 2)}
    roll_q = {"x": 0.0, "y": math.sin(roll / 2), "z": 0.0, "w": math.cos(roll / 2)}
    return multiply_quaternions(multiply_quaternions(yaw_q, pitch_q), roll_q)


def angular_distance(a, b):
    qa = normalize_quaternion(a)
    qb = normalize_quaternion(b)
    dot = abs(qa["x"] * qb["x"] + qa["y"] * qb["y"] + qa["z"] * qb["z"] + qa["w"] * qb["w"])
    return 2 * math.acos(_clamp(dot, -1.0, 1.0))


@dataclass
class AirMouseSettings:
    sensitivity: float = 80.0
    deadzone: float = 0.03
    smoothing: float = 0.25
    max_speed: float = 35.0

    def __post_init__(self):
        self.sensitivity = max(0.0, self.sensitivity)
        self.deadzone = max(0.0, self.deadzone)
        self.smoothing = _clamp(self.smoothing, 0.0, 0.95)
        self.max_speed = max(1.0, self.max_speed)


class StableNeutralCalibrator:
    def __init__(self, required_samples=8, max_angle_delta=0.015):
        self.required_samples = max(1, required_samples)
        self.max_angle_delta = max_angle_delta
        self._candidate = None
        self._stable_samples = 0

    def observe(self, q):
        current = normalize_quaternion(q)
        if self._candidate is None:
            self._candidate = current
            self._stable_samples = 1
            return current if self._stable_samples >= self.required_samples else None

        if angular_distance(self._candidate, current) <= self.max_angle_delta:
            self._stable_samples += 1
        else:
            self._candidate = current
            self._stable_samples = 1

        if self._stable_samples >= self.required_samples:
            return current
        return None


class AirMouseMapper:
    def __init__(self, settings):
        self.settings = settings
        self._neutral_inverse = dict(IDENTITY)
        self._has_neutral = False
        self._previous_dx = 0.0
        self._previous_dy = 0.0

    @property
    def has_neutral(self):
        return self._has_neutral

    def set_neutral(self, q):
        self._neutral_inverse = inverse_quaternion(q)
        self._has_neutral = True
        self._previous_dx = 0.0
        self._previous_dy = 0.0

    def pointer_delta(self, q):
        if not self._has_neutral:
            return (0.0, 0.0)

        relative = multiply_quaternions(self._neutral_inverse, q)
        euler = quaternion_to_euler(relative)
        dx = -self._axis_to_velocity(euler["yaw"])
        dy = -self._axis_to_velocity(euler["pitch"])
        dx, dy = self._clamp_speed(dx, dy)
        dx, dy = self._smooth(dx, dy)

        if abs(dx) < 0.0001:
            dx = 0.0
        if abs(dy) < 0.0001:
            dy = 0.0

        return (round(dx, 4), round(dy, 4))

    def _axis_to_velocity(self, radians):
        if abs(radians) < self.settings.deadzone:
            return 0.0

        direction = 1 if radians > 0 else -1
        adjusted = abs(radians) - self.settings.deadzone
        return direction * adjusted * self.settings.sensitivity

    def _clamp_speed(self, dx, dy):
        magnitude = math.hypot(dx, dy)
        if magnitude <= self.settings.max_speed:
            return dx, dy

        scale = self.settings.max_speed / magnitude
        return dx * scale, dy * scale

    def _smooth(self, dx, dy):
        weight = self.settings.smoothing
        smoothed_dx = self._previous_dx * weight + dx * (1 - weight)
        smoothed_dy = self._previous_dy * weight + dy * (1 - weight)
        self._previous_dx = smoothed_dx
        self._previous_dy = smoothed_dy
        return smoothed_dx, smoothed_dy


class MacMouseController:
    def __init__(self):
        if platform.system() != "Darwin":
            raise RuntimeError("The air mouse pointer backend is macOS-only in v1.")

        self._cg = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        self._cg.CGEventCreate.argtypes = [ctypes.c_void_p]
        self._cg.CGEventCreate.restype = ctypes.c_void_p
        self._cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        self._cg.CGEventGetLocation.restype = CGPoint
        self._cg.CGWarpMouseCursorPosition.argtypes = [CGPoint]
        self._cg.CGAssociateMouseAndMouseCursorPosition.argtypes = [ctypes.c_int]
        self._cg.CFRelease.argtypes = [ctypes.c_void_p]

    def move_relative(self, dx, dy):
        if dx == 0 and dy == 0:
            return

        location = self._current_location()
        self._cg.CGAssociateMouseAndMouseCursorPosition(1)
        self._cg.CGWarpMouseCursorPosition(CGPoint(location.x + dx, location.y + dy))

    def _current_location(self):
        event = self._cg.CGEventCreate(None)
        if not event:
            raise RuntimeError("Unable to read the current mouse location.")

        try:
            return self._cg.CGEventGetLocation(event)
        finally:
            self._cg.CFRelease(event)


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class AirMouseClient:
    def __init__(self, server_url, mapper, mouse, calibrator):
        self.server_url = server_url
        self.mapper = mapper
        self.mouse = mouse
        self.calibrator = calibrator
        self.running = True

    async def run(self):
        logger.info("Connecting to %s", self.server_url)
        async for websocket in websockets.connect(self.server_url, close_timeout=10):
            try:
                logger.info("Connected. Hold the phone still to calibrate neutral.")
                async for message in websocket:
                    if not self.running:
                        return
                    await self._handle_message(message)
            except websockets.exceptions.ConnectionClosed:
                logger.info("Connection closed. Reconnecting...")
                continue

    async def _handle_message(self, message):
        data = json.loads(message)
        if data.get("type") != "orientation" or not isinstance(data.get("quaternion"), dict):
            return

        q = data["quaternion"]
        if not self.mapper.has_neutral:
            neutral = self.calibrator.observe(q)
            if neutral:
                self.mapper.set_neutral(neutral)
                logger.info("Neutral pose calibrated. Move the phone to control the cursor.")
            return

        dx, dy = self.mapper.pointer_delta(q)
        self.mouse.move_relative(dx, dy)

    def stop(self):
        self.running = False


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Use phone orientation as a macOS air mouse.")
    parser.add_argument("--server", default="ws://localhost:8765/", help="Dashboard WebSocket URL")
    parser.add_argument("--sensitivity", type=float, default=80.0, help="Pixels per radian")
    parser.add_argument("--deadzone", type=float, default=0.03, help="Radians ignored around neutral")
    parser.add_argument("--smoothing", type=float, default=0.25, help="0.0 immediate, higher is smoother")
    parser.add_argument("--max-speed", type=float, default=35.0, help="Maximum pixels per sensor update")
    parser.add_argument("--stable-samples", type=int, default=8, help="Samples required before neutral capture")
    return parser


async def main():
    args = build_arg_parser().parse_args()
    settings = AirMouseSettings(
        sensitivity=args.sensitivity,
        deadzone=args.deadzone,
        smoothing=args.smoothing,
        max_speed=args.max_speed,
    )
    client = AirMouseClient(
        server_url=args.server,
        mapper=AirMouseMapper(settings),
        mouse=MacMouseController(),
        calibrator=StableNeutralCalibrator(required_samples=args.stable_samples),
    )

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
