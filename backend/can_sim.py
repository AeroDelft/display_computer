import os
import re
import time
from pathlib import Path
import can
import cantools

# this is terrible fix if time lol
 
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

def main():

    bus = can.interface.Bus(
        interface="virtual",
        channel="sim",
        receive_own_messages=False,
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


if __name__ == "__main__":
    main()