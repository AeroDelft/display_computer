
import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path

import can
import cantools
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

app = FastAPI()

CAN_SIM = True

ROOT_DIR = Path(__file__).resolve().parents[1]
DBC_DIR = ROOT_DIR / "assets" / "dbc_files"
ASC_LOG_PATH = ROOT_DIR / "assets" / "test_log" / "13_02_26_4_success.asc"
CSV_DIR = ROOT_DIR / "assets" / "logs"

db = cantools.database.Database()

for file in os.listdir(DBC_DIR):
    if file.endswith(".dbc"):
        db.add_dbc_file(str(DBC_DIR / file))
        print("Loaded:", file)


def make_csv_path() -> Path:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("[%Y-%m-%d]__[%H-%M-%S]")
    return CSV_DIR / f"{timestamp}__can_log.csv"


async def replay_asc_log(tx_bus: can.BusABC, stop_event: asyncio.Event):
  
    reader = can.ASCReader(str(ASC_LOG_PATH))

    previous_timestamp = None

    for msg in reader:
        if stop_event.is_set():
            break

        if previous_timestamp is not None:
            delay = msg.timestamp - previous_timestamp
            if delay > 0:
                await asyncio.sleep(min(delay, 0.25))

        previous_timestamp = msg.timestamp

        try:
            tx_bus.send(msg)
        except can.CanError as e:
            print("CAN send error:", e)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    csv_path = make_csv_path()
    diagnostics = []
    unknown_msg = 0
    stop_event = asyncio.Event()

    if CAN_SIM:
        tx_bus = can.interface.Bus(
            interface="virtual",
            channel="test",
            receive_own_messages=False,
        )

        rx_bus = can.interface.Bus(
            interface="virtual",
            channel="test",
            receive_own_messages=False,
        )

        print("Using simulated CAN")

    else:
        possible_interfaces = [
            interface
            for interface in can.detect_available_configs()
            if "pcan" in interface["interface"]
        ]

        if not possible_interfaces:
            raise RuntimeError("No PCAN interfaces found.")

        rx_bus = can.interface.Bus(
            channel=possible_interfaces[0]["channel"],
            interface=possible_interfaces[0]["interface"],
        )

        tx_bus = None
        print("Using real CAN:", possible_interfaces[0])

    can_reader = can.AsyncBufferedReader()

    notifier = can.Notifier(
        rx_bus,
        [can_reader],
        loop=asyncio.get_running_loop(),
    )

    replay_task = None

    if CAN_SIM:
        replay_task = asyncio.create_task(replay_asc_log(tx_bus, stop_event))

    try:
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["time", "signal", "value"])

            print("Listening for CAN messages...")

            while True:
                msg = await can_reader.get_message()
                print("msg_recieved")

                try:
                    can_id = msg.arbitration_id
                    decoded = db.decode_message(can_id, msg.data)
                    msg_def = db.get_message_by_frame_id(can_id)

                    name = (
                        msg_def.name.replace("NDCDC", "DCMP_")
                        .replace("dcdc", "DCHV_")
                        .replace("user", "MS100")
                    )

                    for signal_name, value in decoded.items():
                        full_signal_name = f"{name}.{signal_name}"
                        writer.writerow(
                            [f"{msg.timestamp:.6f}", full_signal_name, value]
                        )

                    await websocket.send_json(
                        {
                            "can_id": hex(can_id),
                            "message_name": name,
                            "signals": decoded,
                            "diagnostics": diagnostics[-20:],
                        }
                    )

                except (cantools.database.errors.DecodeError, KeyError) as e:
                    unknown_msg += 1

                    diagnostics.append(
                        {
                            "type": "decode_error",
                            "can_id": hex(msg.arbitration_id),
                            "error": str(e),
                        }
                    )

                    print(
                        f"Unknown message: ID {hex(msg.arbitration_id)}, "
                        f"data={msg.data.hex()}"
                    )

    except WebSocketDisconnect:
        print("Client disconnected")

    finally:
        stop_event.set()

        if replay_task:
            replay_task.cancel()

        notifier.stop()
        rx_bus.shutdown()

        if tx_bus:
            tx_bus.shutdown()

        print("Stopped CAN WebSocket cleanly.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)