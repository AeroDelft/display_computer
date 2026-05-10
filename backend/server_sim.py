from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
from pathlib import Path
import os
import cantools
import can


app = FastAPI()

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

@app.websocket("/ws") #create a websocket endpoint for the frontend to connect to
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:

        for msg in can_bus:  # continuous loop
            
            try: 

                    try:

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

                        if decoded:
                            await websocket.send_json(
                                {
                                    "can_id": hex(can_id),
                                    "signals": decoded,
                                    "diagnostics": diagnostics,
                                }
                    )
                

                    except WebSocketDisconnect:
                        print("Client disconnected")

            
            except (cantools.database.errors.DecodeError, KeyError) as e:
                # ignore unknown/partial messages
                unknown_msg += 1
                print(f"Unknown message: ID {msg.arbitration_id}, data {msg.data.hex()}")
                diagnostics.append({"type": "decode_error", "can_id": hex(msg.arbitration_id), "error": str(e)})
                pass

    except KeyboardInterrupt:
        print("\nStopped by user")