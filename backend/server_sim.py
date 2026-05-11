from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
from pathlib import Path
import os
import cantools
import can
import logging 
import re
import time



app = FastAPI()

ROOT_DIR = Path(__file__).resolve().parents[1]

DBC_FILES = [
    ROOT_DIR / "assets" / "dbc_files" / "BLS_046_00_MSG_00.dbc",
    ROOT_DIR / "assets" / "dbc_files" / "BLS_102_00_MSG_00.dbc",
    ROOT_DIR / "assets" / "dbc_files" / "External_Coms.dbc",
]
LOG_RE = re.compile(
        r"(\d+:\d+:\d+:\d+)\s+\w+\s+\d+\s+(0x[0-9A-Fa-f]+)\s+([sx])r?\s+(\d+)((?:\s+[0-9A-Fa-f]{2})*)")



def parse_log_line(line: str):
    """Returns (timestamp_ms, can_id, is_extended, data_bytes) or None."""
    m = LOG_RE.match(line.strip())
    if not m:
        return None

    ts_str, id_str, frame_type, dlc_str, data_str = m.groups()

    # Parse timestamp → milliseconds-of-day (good enough for relative replay)
    hh, mm, ss, ms = map(int, ts_str.split(":"))
    ts_ms = ((hh * 3600 + mm * 60 + ss) * 1000) + ms

    can_id = int(id_str, 16)
    extended = frame_type == "x"

    if extended:
        # Mask any "extended frame flag bit" if BusMaster encodes it in the top bit.
        can_id &= 0x1FFFFFFF

    data_hex = data_str.split()
    data      = bytes(int(b, 16) for b in data_hex)

    return ts_ms, can_id, extended, data

def iter_log_frames(log_file: Path):
    """
    Yield (timestamp_ms, can_id, data_bytes) from a BusMaster log.
    This is the offline source for development until a real CAN interface is connected.
    """
    with open(log_file, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            parsed = parse_log_line(raw_line)
            if parsed is None:
                continue
            ts_ms, can_id, _extended, data = parsed
            yield ts_ms, can_id, data

def can_sim_send():
    
    bus = can.interface.Bus(
        interface="virtual",
        channel="test"
    )
   

    # For offline testing (until CAN integration is connected)
    LOG_FILE = Path(
        os.environ.get(
            "DISPLAY_COMPUTER_LOG_FILE",
            str(ROOT_DIR / "assets" / "logs" / "13_02_26_4_success.log"),
        )
    )

    prev_ts = None
    sent_count = 0

    for timestamp_ms, can_id, data_bytes in iter_log_frames(LOG_FILE):

        if prev_ts is not None:
            delta = (timestamp_ms - prev_ts) / 1000.0

            if 0 < delta < 2.0:
                time.sleep(delta)

        prev_ts = timestamp_ms

        msg = can.Message(
            arbitration_id=can_id,
            data=data_bytes,
            check=True,
        )

        bus.send(msg)
        sent_count += 1

        print(
            f"Sent #{sent_count}: "
            f"ID={hex(can_id)} "
            f"data={data_bytes.hex(' ')}"
        )

can_sim = True

ROOT_DIR = Path(__file__).resolve().parents[1]
DBC_DIR = ROOT_DIR / "assets" / "dbc_files"

#load dbcs
dbc_files = []
db = cantools.database.Database()
for file in os.listdir(DBC_DIR):
    if file.endswith(".dbc"):
        dbc_files.append(file)
        db.add_dbc_file(f"{DBC_DIR}/{file}")
        print("Loaded:", {file})



if can_sim == True:
    can_bus = can.interface.Bus(
        interface="virtual",
        channel="test"
    ) 

    reader = can.AsyncBufferedReader()
    print("Using simulated CAN")

else:
    # hunt for a peak can connection
    possible_interfaces = []
    for interface in can.detect_available_configs():
        if "pcan" in interface["interface"]:
            possible_interfaces.append(interface)
            print(
                f"\nFound PCAN interface: {interface['interface']} with channel {interface['channel']}\n"
            )

    if len(possible_interfaces) == 0:
        raise Exception("No PCAN interfaces found.")


    # open CAN bus with the first detected PCAN interface
    can_bus = can.interface.Bus(
        channel=possible_interfaces[0]["channel"],
        interface=possible_interfaces[0]["interface"],
    )
    print("Using real CAN")

print("Listening for CAN messages")
unknown_msg = 0
diagnostics: list[dict] = []

# @app.websocket("/ws") #create a websocket endpoint for the frontend to connect to
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
try:
    # while True: 
        # msg = await reader.get_message() 
        # msg = await asyncio.to_thread(can_bus.recv)
    for msg in can_bus:  # continuous loop
        
        try: 

                # try:

                    can_id = msg.arbitration_id

                    decoded = db.decode_message(can_id, msg.data) #use cantools to decode the message
                    msg_def = db.get_message_by_frame_id(can_id)

                    print(can_id)
                    # Compute display name - probably not necessary for frontend
                    name = (
                        msg_def.name.replace("NDCDC", "DCMP_")
                        .replace("dcdc", "DCHV_")
                        .replace("user", "MS100")
                    )

                    for signal_name, value in decoded.items():
                        full_signal_name = f"{name}.{signal_name}"

                    # if decoded:
                    #     await websocket.send_json(
                    #         {
                    #             "can_id": hex(can_id),
                    #             "signals": decoded,
                    #             "diagnostics": diagnostics,
                    #         }
                # )
            

                # except WebSocketDisconnect:
                #     print("Client disconnected")

        
        except (cantools.database.errors.DecodeError, KeyError) as e:
            # ignore unknown/partial messages
            unknown_msg += 1
            print(f"Unknown message: ID {msg.arbitration_id}, data {msg.data.hex()}")
            diagnostics.append({"type": "decode_error", "can_id": hex(msg.arbitration_id), "error": str(e)})
            pass

except KeyboardInterrupt:
    print("\nStopped by user")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)