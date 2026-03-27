declare global {
    const echarts: any
  }
export type CANMessage = {
    id: number
    value: number | {
        name: string
        severity: "amber" | "red"
    }
  }