import asyncio
import csv
import logging
import os
from datetime import datetime
from pathlib import Path

import can
import cantools
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

# Configure logging
# To enable DEBUG logging, change level to logging.DEBUG
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI()

ROOT_DIR = Path(__file__).resolve().parents[1]
DBC_DIR = ROOT_DIR / "assets" / "dbc_files"

db = cantools.database.Database()
for file in os.listdir(DBC_DIR):
    if file.endswith(".dbc"):
        db.add_dbc_file(f"{DBC_DIR}/{file}")
        logger.info(f"Loaded DBC file: {file}")

filename = "KWB-Integrated-Testing"
timestamp_str = datetime.now().strftime("[%Y-%m-%d]__[%H-%M]__")
os.makedirs(ROOT_DIR / "assets", exist_ok=True)
csv_path = ROOT_DIR / "assets" / f"{timestamp_str}[{filename}].csv"

can_bus = can.interface.Bus(
    channel="can0", interface="socketcan", recv_own_messages=False
)
logger.info(f"CAN bus initialized on channel vcan0")
logger.info(f"CSV logging to: {csv_path}")

unknown_msg = 0
diagnostics = []
csvfile = open(csv_path, "w", newline="")
writer = csv.writer(csvfile)
writer.writerow(["time", "signal", "value"])
csvfile.flush()  # Ensure header is written immediately

# Counter for periodic unknown message logging
message_count = 0
REPORT_INTERVAL = 100  # Report unknown messages every N messages


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global unknown_msg, message_count

    await websocket.accept()
    logger.info("WebSocket client connected")
    loop = asyncio.get_event_loop()

    try:
        while True:
            msg = await loop.run_in_executor(None, can_bus.recv)
            if msg is None:
                continue

            message_count += 1
            logger.debug(
                f"Received CAN message: ID={hex(msg.arbitration_id)}, Data={msg.data.hex()}"
            )

            try:
                can_id = msg.arbitration_id
                decoded = db.decode_message(can_id, msg.data)
                msg_def = db.get_message_by_frame_id(can_id)
                name = (
                    msg_def.name.replace("NDCDC", "DCMP_")
                    .replace("dcdc", "DCHV_")
                    .replace("user", "MS100")
                )

                logger.debug(
                    f"Successfully decoded message {name} (ID={hex(can_id)}): {decoded}"
                )

                # Write to CSV
                for signal_name, value in decoded.items():
                    full_signal_name = f"{name}.{signal_name}"
                    writer.writerow([f"{msg.timestamp:.6f}", full_signal_name, value])

                # Flush CSV to ensure data is saved
                csvfile.flush()

                if decoded:
                    json_data = {
                        "can_id": hex(can_id),
                        "signals": decoded,
                        "diagnostics": diagnostics,
                    }
                    await websocket.send_json(json_data)
                    logger.info(
                        f"Sent CAN ID {hex(can_id)} with {len(decoded)} signals to WebSocket"
                    )
                    logger.debug(f"JSON payload: {json_data}")

            except cantools.database.errors.DecodeError as e:
                unknown_msg += 1
                logger.debug(f"DecodeError for CAN ID {hex(msg.arbitration_id)}: {e}")

            except KeyError as e:
                unknown_msg += 1
                logger.debug(f"KeyError for CAN ID {hex(msg.arbitration_id)}: {e}")

            except Exception as e:
                unknown_msg += 1
                logger.warning(
                    f"Unexpected error decoding CAN ID {hex(msg.arbitration_id)}: {type(e).__name__}: {e}"
                )

            # Periodically report unknown message count
            if message_count % REPORT_INTERVAL == 0:
                logger.info(
                    f"Status: Processed {message_count} messages, {unknown_msg} unknown ({unknown_msg / message_count * 100:.1f}%)"
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        # Ensure CSV is flushed on disconnect
        csvfile.flush()
