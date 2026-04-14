// -----------------------------------------------------------------------
// decoder.ts
//
// Translates raw WebSocket messages from the server into dashboard keys.
//
// The server sends two shapes:
//
//   Shape A – decoded CAN frame (from the log replayer):
//     { can_id: "0x702", signals: { TDCDCSR1Measured: 65.3, ... } }
//
//   Shape B – legacy simulator message (integer id + value):
//     { id: 102, value: 60 }
//
// Both shapes produce the same output type so main.ts doesn't care
// which source is active.
// -----------------------------------------------------------------------
// Map from DBC signal name → dashboard key.
//
// These come from the BLS_046 and BLS_102 DBC files.
// Edit this table to decide which signals feed which gauges / panels.
// All available signal names are listed as comments so you can swap them in.
//
// BLS_046 signals (DCDC temperatures, voltages, state)
// ─────────────────────────────────────────────────────
//   Temperatures (°C):  TDCDCSR1Measured, TDCDCSR2Measured,
//                       TDCDCBB1Measured, TDCDCBB2Measured,
//                       TDCDCBB3Measured, TDCDCBB4Measured
//   HV voltage (V):     VDCDCHVAverage
//   SR voltages (V):    VDCDCSRMin, VDCDCSRMax, VDCDCSRAverage
//   HV current (A):     IDCDCHVAverage
//   LV1 voltage (V):    VDCDCLV1Min, VDCDCLV1Max, VDCDCLV1Average
//   LV1 current (A):    IDCDCLV1Average, IDCDCLV1UnBalance
//   LV2 voltage (V):    VDCDCLV2Min, VDCDCLV2Max, VDCDCLV2Average
//   LV2 current (A):    IDCDCLV2Average, IDCDCLV2UnBalance
//   Aux voltages (V):   VDCDCAux1Measured … VDCDCAux5Measured
//   State:              NDCDCState  (0=init 1=sleep 2=disabled 4=off 8=on 15=fault)
//
// BLS_102 signals (multi-path DCDC node values)
// ──────────────────────────────────────────────
//   Port A voltages (V):   VPortA1Average … VPortA6Average
//   Port A currents (A):   IPortA1Average … IPortA6Average
//   Port B1 voltage (V):   VPortB1Average, VPortB1Min, VPortB1Max
//   Port B1 current (A):   IPortB1Average
//   Port B2 voltage (V):   VPortB2Average, VPortB2Min, VPortB2Max
//   Port B2 current (A):   IPortB2Average
//   Cell temperatures (°C):TCell1N1 … TCell8N1, TCell1N2 … TCell8N2
//   Internal temp (°C):    TInternal
//   Aux voltages (V):      VAux1Measured, VAux2Measured, VAux3Measured
//   Module state:          NModuleState, NPath1State … NPath6State
const SIGNAL_MAP = {
    // 0x703 (NDCDCValue) – temperatures °C
    TDCDCSR1Measured: "motor_temp",
    TDCDCSR2Measured: "fc_temp",
    TDCDCBB1Measured: "coolant_temp",
    TDCDCBB2Measured: "tank_temp",
    TDCDCBB3Measured: "fp_temp",
    // 0x703 (NDCDCValue) – voltages
    VDCDCSRAverage: "motor_power",
    VDCDCHVAverage: "pressure",
    // 0x1002 / 0x1003 (DcdcNode GlobalValue) – cell temperatures
    TInternal: "fc_temp",
    TCell1N1: "motor_temp",
    TCell2N1: "coolant_temp",
    TCell3N1: "tank_temp",
    TCell4N1: "fp_temp",
    // 0x1042 / 0x1043 (DcdcNode GlobalValue) – aux voltages
    VAux1Measured: "motor_power",
    // 0x701 (NDCDCSetpoints)
    VDCDCHVSetpoint: "pressure",
    IDCDCLV1Average: "consumption",
    VDCDCLV1Average: "fuel_percent",
};
// Track rising edge per warning signal so log replay doesn't spam duplicates.
const warningActiveBySignal = {};
// Optional: override DBC fault/warning signals to control UI naming + severity.
// Add entries as you learn which signals you actually care about.
const WARNING_OVERRIDES = {};
function severityFromSignalName(sigName) {
    // Simple heuristic:
    // - *Warning* => amber
    // - *Error* => red
    if (sigName.includes("Warning"))
        return "amber";
    if (sigName.includes("Error"))
        return "red";
    return null;
}
function maybeEmitWarning(sigName, rawValue) {
    const override = WARNING_OVERRIDES[sigName];
    const severity = override ? override.severity : severityFromSignalName(sigName);
    if (!severity)
        return null;
    const active = rawValue !== 0;
    const wasActive = (sigName in warningActiveBySignal) ? warningActiveBySignal[sigName] : false;
    warningActiveBySignal[sigName] = active;
    if (active && !wasActive) {
        const name = override && override.name ? override.name : sigName;
        return { key: "warning", value: { name, severity } };
    }
    return null;
}
// -----------------------------------------------------------------------
// decodeMessage
//
// Accepts either message shape and returns an array of DecodedItems
// (one per signal that has a mapping).  Returns [] for unknown messages.
// -----------------------------------------------------------------------
export function decodeMessage(msg) {
    const results = [];
    // ── Shape A: live log replay from server ──────────────────────────────
    // { can_id: "0x702", signals: { SignalName: number, ... } }
    if (msg && typeof msg.can_id === "string" && typeof msg.signals === "object") {
        const signals = msg.signals;
        for (const [sigName, rawValue] of Object.entries(signals)) {
            const dashKey = SIGNAL_MAP[sigName];
            if (dashKey) {
                results.push({
                    key: dashKey,
                    value: rawValue,
                });
            }
            const warn = maybeEmitWarning(sigName, rawValue);
            if (warn)
                results.push(warn);
        }
        return results;
    }
    // ── Shape B: legacy simulator messages ───────────────────────────────
    // { id: number, value: number | { name, severity } }
    if (msg && typeof msg.id === "number") {
        switch (msg.id) {
            // Gauges
            case 101:
                results.push({ key: "motor_power", value: msg.value });
                break;
            case 102:
                results.push({ key: "motor_temp", value: msg.value });
                break;
            case 103:
                results.push({ key: "fc_temp", value: msg.value });
                break;
            case 104:
                results.push({ key: "coolant_temp", value: msg.value });
                break;
            case 105:
                results.push({ key: "tank_temp", value: msg.value });
                break;
            case 106:
                results.push({ key: "fp_temp", value: msg.value });
                break;
            case 107:
                results.push({ key: "max_temp", value: msg.value });
                break;
            // Hydrogen panel
            case 201:
                results.push({ key: "ambient_h2", value: msg.value });
                break;
            case 202:
                results.push({ key: "fuel_percent", value: msg.value });
                break;
            case 203:
                results.push({ key: "mass", value: msg.value });
                break;
            case 204:
                results.push({ key: "pressure", value: msg.value });
                break;
            case 205:
                results.push({ key: "consumption", value: msg.value });
                break;
            case 206:
                results.push({ key: "time_left", value: msg.value });
                break;
            // Warnings
            case 300: {
                const w = msg.value;
                const name = w && typeof w.name === "string" ? w.name : undefined;
                const severity = w && (w.severity === "amber" || w.severity === "red") ? w.severity : undefined;
                if (typeof name === "string" && severity && !(name in warningActiveBySignal)) {
                    warningActiveBySignal[name] = true;
                    results.push({ key: "warning", value: { name, severity } });
                }
                break;
            }
        }
    }
    return results;
}
