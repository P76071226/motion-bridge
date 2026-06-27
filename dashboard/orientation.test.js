const assert = require("node:assert/strict");
const test = require("node:test");

const {
  createCalibrationState,
  applyCalibration,
  formatQuaternion,
} = require("./orientation");

test("calibration starts as a pass-through transform", () => {
  const state = createCalibrationState();
  const q = { x: 0.1, y: -0.2, z: 0.3, w: 0.92 };

  assert.deepEqual(formatQuaternion(applyCalibration(q, state)), {
    x: 0.1,
    y: -0.2,
    z: 0.3,
    w: 0.92,
  });
});

test("setting neutral makes the current orientation render as identity", () => {
  const state = createCalibrationState();
  const q = { x: 0.2, y: 0.3, z: -0.1, w: 0.9274 };

  state.setNeutral(q);

  assert.deepEqual(formatQuaternion(applyCalibration(q, state)), {
    x: 0,
    y: 0,
    z: 0,
    w: 1,
  });
});

test("clearing neutral restores raw orientation", () => {
  const state = createCalibrationState();
  const q = { x: -0.12, y: 0.44, z: 0.08, w: 0.8862 };

  state.setNeutral(q);
  state.clearNeutral();

  assert.deepEqual(formatQuaternion(applyCalibration(q, state)), {
    x: -0.12,
    y: 0.44,
    z: 0.08,
    w: 0.8862,
  });
});
