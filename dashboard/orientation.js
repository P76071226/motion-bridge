(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.PhoneOrientation = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  const IDENTITY = { x: 0, y: 0, z: 0, w: 1 };

  function normalizeQuaternion(q) {
    const length = Math.hypot(q.x, q.y, q.z, q.w);
    if (!length) {
      return { ...IDENTITY };
    }

    return {
      x: q.x / length,
      y: q.y / length,
      z: q.z / length,
      w: q.w / length,
    };
  }

  function inverseQuaternion(q) {
    const normalized = normalizeQuaternion(q);
    return {
      x: -normalized.x,
      y: -normalized.y,
      z: -normalized.z,
      w: normalized.w,
    };
  }

  function multiplyQuaternions(a, b) {
    return normalizeQuaternion({
      x: a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
      y: a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
      z: a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
      w: a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
    });
  }

  function createCalibrationState() {
    let neutralInverse = { ...IDENTITY };
    let calibrated = false;

    return {
      get calibrated() {
        return calibrated;
      },
      get neutralInverse() {
        return { ...neutralInverse };
      },
      setNeutral(q) {
        neutralInverse = inverseQuaternion(q);
        calibrated = true;
      },
      clearNeutral() {
        neutralInverse = { ...IDENTITY };
        calibrated = false;
      },
    };
  }

  function applyCalibration(q, state) {
    if (!state.calibrated) {
      return { ...q };
    }

    return multiplyQuaternions(state.neutralInverse, q);
  }

  function roundNearZero(value) {
    const rounded = Number(value.toFixed(4));
    return Object.is(rounded, -0) ? 0 : rounded;
  }

  function formatQuaternion(q) {
    return {
      x: roundNearZero(q.x),
      y: roundNearZero(q.y),
      z: roundNearZero(q.z),
      w: roundNearZero(q.w),
    };
  }

  return {
    createCalibrationState,
    applyCalibration,
    formatQuaternion,
    inverseQuaternion,
    multiplyQuaternions,
    normalizeQuaternion,
  };
});
