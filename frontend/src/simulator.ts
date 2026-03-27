import type { CANMessage } from "./types"

export function startSimulator(callback: (msg: CANMessage) => void) {

  console.log("Simulator running")

  function send(id: number, value: number) {

    const msg: CANMessage = {
      id: id,
      value: Math.round(value)
    }
  
    console.log("SIM:", msg)
  
    callback(msg)
  }

  let t = 0

  setInterval(() => {

    t += 0.1

    // Gauges
    send(101, 50 + 40 * Math.sin(t))
    send(102, 60 + 30 * Math.sin(t * 0.7))
    send(103, 55 + 20 * Math.sin(t * 0.5))
    send(104, 65 + 10 * Math.sin(t * 0.9))
    send(105, 50 + 15 * Math.sin(t * 0.3))
    send(106, 45 + 20 * Math.sin(t * 0.8))
    send(107, 80 + 30 * Math.sin(t * 0.4))

    // Hydrogen system
    send(201, 0.2 + 0.1 * Math.sin(t))
    send(202, 60 + 30 * Math.sin(t * 0.2))

  }, 50)

  setInterval(() => {

    const warnings = [
      { name: "FC TEMP HIGH", severity: "amber" },
      { name: "HYDROGEN LEAK", severity: "red" },
      { name: "LOW PRESSURE", severity: "amber" },
      { name: "COOLANT TEMP HIGH", severity: "red" }
    ] as const
  
    const w = warnings[Math.floor(Math.random() * warnings.length)]
  
    callback({
      id: 300,
      value: w
    })
  
  }, 4000)

}
