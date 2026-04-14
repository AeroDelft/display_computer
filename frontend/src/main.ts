import { createGauge } from "./gauges.js"
import { connectWebSocket } from "./websocket.js"
import { addWarning } from "./warnings.js"
import { decodeMessage } from "./decoder.js"
// import { startSimulator } from "./simulator.js"   // ← keep if you want to
                                                      //   switch back to sim


// ─────────────────────────────────────────────────────────────────────────────
// GAUGES
// ─────────────────────────────────────────────────────────────────────────────

const motorPowerGauge = createGauge("motor_power", 0, 100, [
  [0.6, "#ffffff"],
  [0.8, "#ffb300"],
  [1,   "#ff0000"],
])

const motorTempGauge = createGauge("motor_temp", 0, 100, [
  [0.5,  "#ffffff"],
  [0.75, "#ffb300"],
  [1,    "#ff0000"],
])

const fcTempGauge = createGauge("fc_temp", 0, 100, [
  [0.5,  "#ffffff"],
  [0.75, "#ffb300"],
  [1,    "#ff0000"],
])

const coolantTempGauge = createGauge("coolant_temp", 0, 100, [
  [0.5,  "#ffffff"],
  [0.75, "#ffb300"],
  [1,    "#ff0000"],
])

const tankTempGauge = createGauge("tank_temp", 0, 100, [
  [0.5,  "#ffffff"],
  [0.75, "#ffb300"],
  [1,    "#ff0000"],
])

const fpTempGauge = createGauge("fp_temp", 0, 100, [
  [0.5,  "#ffffff"],
  [0.75, "#ffb300"],
  [1,    "#ff0000"],
])

const maxTempGauge = createGauge("max_temp", 0, 120, [
  [0.5,  "#ffffff"],
  [0.75, "#ffb300"],
  [1,    "#ff0000"],
])

const placeholderGauge = createGauge("placeholder", 0, 120, [
  [0.5,  "#ffffff"],
  [0.75, "#ffb300"],
  [1,    "#ff0000"],
])

// Lookup table: dashboard key → gauge instance
const gauges = {
  motor_power:  motorPowerGauge,
  motor_temp:   motorTempGauge,
  fc_temp:      fcTempGauge,
  coolant_temp: coolantTempGauge,
  tank_temp:    tankTempGauge,
  fp_temp:      fpTempGauge,
  max_temp:     maxTempGauge,
}

// Tracked so we can derive max_temp ourselves when the source is the log replayer
const temps = {
  motor_temp:   0,
  fc_temp:      0,
  coolant_temp: 0,
  tank_temp:    0,
  fp_temp:      0,
}
const TEMP_KEYS = Object.keys(temps) as (keyof typeof temps)[]


// ─────────────────────────────────────────────────────────────────────────────
// HELPER – update a single decoded item on the dashboard
// ─────────────────────────────────────────────────────────────────────────────

function applyDecoded(key: string, value: any) {

  // ── Gauge update ─────────────────────────────────────────────────────
  const gauge = gauges[key as keyof typeof gauges]
  if (gauge) {
    gauge.setOption({ series: [{ data: [{ value }] }] })
  }

  // ── Temperature tracking → derive max_temp ───────────────────────────
  if ((TEMP_KEYS as string[]).includes(key)) {
    temps[key as keyof typeof temps] = value as number
    const max = Math.max(...TEMP_KEYS.map(k => temps[k]))
    maxTempGauge.setOption({ series: [{ data: [{ value: max }] }] })
  }

  // ── Hydrogen / info panel ────────────────────────────────────────────
  switch (key) {

    case "ambient_h2":
      document.getElementById("ambient_value")!.innerText =
        (value as number).toFixed(2) + "%"
      break

    case "fuel_percent":
      document.getElementById("fuel_level")!.style.height =
        value + "%"
      break

    case "mass":
      document.getElementById("mass_value")!.innerText =
        (value as number).toFixed(2) + " kg"
      break

    case "pressure":
      document.getElementById("pressure_value")!.innerText =
        (value as number).toFixed(1) + " bar"
      break

    case "consumption":
      document.getElementById("consumption_value")!.innerText =
        (value as number).toFixed(3) + " kg/s"
      break

    case "time_left":
      document.getElementById("time_value")!.innerText =
        value + " s"
      break

    case "warning":
      addWarning(value.name, value.severity)
      break
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// RECEIVE TELEMETRY  (log replayer via WebSocket)
// ─────────────────────────────────────────────────────────────────────────────

connectWebSocket((msg) => {
  console.log("WS message:", msg)   
  const items = decodeMessage(msg)   // always returns an array now
  for (const item of items) {
    applyDecoded(item.key, item.value)
  }
})


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