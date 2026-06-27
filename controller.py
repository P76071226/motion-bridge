import math


def _clamp(value, minimum=-1.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def _round_axis(value):
    rounded = round(_clamp(value), 4)
    return 0.0 if rounded == -0.0 else rounded


def quaternion_to_euler(q):
    x = q["x"]
    y = q["y"]
    z = q["z"]
    w = q["w"]

    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    pitch = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        roll = math.copysign(math.pi / 2, sinp)
    else:
        roll = math.asin(sinp)

    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return {"yaw": yaw, "pitch": pitch, "roll": roll}


def quaternion_to_controller_axes(q):
    euler = quaternion_to_euler(q)

    return {
        "yaw": _round_axis(euler["yaw"] / math.pi),
        "pitch": _round_axis(euler["pitch"] / (math.pi / 2)),
        "roll": _round_axis(euler["roll"] / (math.pi / 2)),
    }


def build_controller_message(q):
    return {
        "type": "controller",
        "axes": quaternion_to_controller_axes(q),
        "quaternion": q,
    }
