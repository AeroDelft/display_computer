import { createGauge } from "./gauges.js";
import { connectWebSocket } from "./websocket.js";
import { addWarning } from "./warnings.js";
import { decodeMessage } from "./decoder.js";
// import { startSimulator } from "./simulator.js"   // ← keep if you want to
//   switch back to sim

// ─────────────────────────────────────────────────────────────────────────────
// GAUGES
// ─────────────────────────────────────────────────────────────────────────────

// Motor power gauge – unit is kW, derived from torque × ω
const motorPowerGauge = createGauge("motor_power", 0, 100, [
  [0.16666667, "#ffffff"],
  [0.3, "#ffb300"],
  [0.9, "#a0db7e"],
  [0.95, "#ff0000"],
]);
const motorTempGauge = createGauge("motor_temp", 0, 100, [
  [0.6, "#ffffff"],
  [0.75, "#ffb300"],
  [1, "#ff0000"],
]);
const fcTempGauge = createGauge("fc_temp", -10, 100, [
  [0.85, "#ffffff"],
  [0.9, "#ffb300"],
  [1, "#ff0000"],
]);

// need values for this from andreas
const coolantTempGauge = createGauge("coolant_temp", -10, 100, [
  [0.5, "#ffffff"],
  [0.85, "#ffb300"],
  [0.9, "#ff0000"],
]);

const tankTempGauge = createGauge("tank_temp", -50, 100, [
  [0.09, "#ff0000"],
  [0.133333, "#ffb300"],
  [0.853333, "#ffffff"],
  [0.88667, "#ffb300"],
  [1, "#ff0000"],
]);
//what even is this
const fpTempGauge = createGauge("fp_temp", 0, 100, [
  [0.5, "#ffffff"],
  [0.75, "#ffb300"],
  [1, "#ff0000"],
]);
const maxTempGauge = createGauge("max_temp", -10, 250, [
  [0.4, "#ffffff"],
  [0.6, "#ffb300"],
  [0.8, "#ff0000"],
]);
const medPresGauge = createGauge("med_pres", 0, 20, [
  [0.4, "#ffffff"],
  [0.6, "#a0db7e"],
  [0.8, "#ffb300"],
  [1.0, "#ff0000"],
]);


// Lookup table: dashboard key → gauge instance
const gauges = {
  motor_power: motorPowerGauge,
  motor_temp: motorTempGauge,
  fc_temp: fcTempGauge,
  coolant_temp: coolantTempGauge,
  tank_temp: tankTempGauge,
  fp_temp: fpTempGauge,
  max_temp: maxTempGauge,
  med_pres: medPresGauge,
};

// Tracked to derive motor_power = torque × (rpm × 2π/60) / 1000  [kW]
const motorComponents = {
  motor_torque: 0, // Nm
  motor_rpm: 0,   // RPM
};
const MOTOR_KEYS = Object.keys(motorComponents) as (keyof typeof motorComponents)[];

// Tracked to derive max_temp = max of the 4 VCU ambient temperature sensors
const ambTemps = {
  amb_temp_0: 0,
  amb_temp_1: 0,
  amb_temp_2: 0,
  amb_temp_3: 0,
};
const AMB_TEMP_KEYS = Object.keys(ambTemps) as (keyof typeof ambTemps)[];

// ─────────────────────────────────────────────────────────────────────────────
// HELPER – update a single decoded item on the dashboard
// ─────────────────────────────────────────────────────────────────────────────

function applyDecoded(key: string, value: any) {
  console.log(value);
  // ── Motor power derivation (torque × ω) ───────────────────────────────────────────────
  if ((MOTOR_KEYS as string[]).includes(key)) {
    motorComponents[key as keyof typeof motorComponents] = value as number;
    const omega = motorComponents.motor_rpm * (2 * Math.PI / 60); // rad/s
    const powerKW = (motorComponents.motor_torque * omega) / 1000;
    motorPowerGauge.setOption({ series: [{ data: [{ value: Math.round(powerKW * 10) / 10 }] }] });
  }

  // ── Gauge update ─────────────────────────────────────────────────────────────────────
  const gauge = gauges[key as keyof typeof gauges];
  if (gauge) {
    gauge.setOption({ series: [{ data: [{ value: value }] }] });
  }

  // ── Ambient temperature tracking → derive max_temp ───────────────────
  if ((AMB_TEMP_KEYS as string[]).includes(key)) {
    ambTemps[key as keyof typeof ambTemps] = value as number;
    const max = Math.max(...AMB_TEMP_KEYS.map((k) => ambTemps[k]));
    maxTempGauge.setOption({ series: [{ data: [{ value: max }] }] });
  }

  // ── Hydrogen / info panel ────────────────────────────────────────────
  switch (key) {
    case "ambient_h2":
      document.getElementById("ambient_value")!.innerText =
        (value as number).toFixed(2) + "%";
      break;

    case "fuel_percent":
      document.getElementById("fuel_level")!.style.height = value + "%";
      break;

    case "mass":
      document.getElementById("mass_value")!.innerText =
        (value as number).toFixed(2) + " kg";
      break;

    case "pressure":
      document.getElementById("pressure_value")!.innerText =
        (value as number).toFixed(1) + " bar";
      break;

    case "consumption":
      document.getElementById("consumption_value")!.innerText =
        (value as number).toFixed(3) + " kg/s";
      break;

    case "time_left":
      document.getElementById("time_value")!.innerText = value + " s";
      break;

    case "warning":
      addWarning(value.name, value.severity);
      break;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// RECEIVE TELEMETRY  (log replayer via WebSocket)
// ─────────────────────────────────────────────────────────────────────────────

connectWebSocket((msg) => {
  const items = decodeMessage(msg); // always returns an array now
  for (const item of items) {
    applyDecoded(item.key, item.value);
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// SIMULATOR  (comment this block back in and comment out connectWebSocket
//             above if you want to test without a real log file)
// ─────────────────────────────────────────────────────────────────────────────

// import type { CANMessage } from "./types"
//
// startSimulator((msg: CANMessage) => {
//   const items = decodeMessage(msg)
//   for (const item of items) {
//     applyDecoded(item.key, item.value)
//   }
// })
