from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
import asyncio
import re
from pathlib import Path

import os
import cantools

app = FastAPI()

# ── DBC loading (use cantools for correct DBC semantics) ──────────────────────

ROOT_DIR = Path(__file__).resolve().parents[1]

DBC_FILES = [
    ROOT_DIR / "assets" / "dbc_files" / "BLS_046_00_MSG_00.dbc",
    ROOT_DIR / "assets" / "dbc_files" / "BLS_102_00_MSG_00.dbc",
    ROOT_DIR / "assets" / "dbc_files" / "External_Coms.dbc",
]

# For offline testing (until CAN integration is connected)
LOG_FILE = Path(
    os.environ.get(
        "DISPLAY_COMPUTER_LOG_FILE",
        str(ROOT_DIR / "assets" / "logs" / "13_02_26_4_success.log"),
    )
)


def load_messages_by_frame_id(dbc_paths: list[Path]) -> dict[int, object]:
    messages_by_frame_id: dict[int, object] = {}
    for dbc_path in dbc_paths:
        db = cantools.database.load_file(str(dbc_path))
        for msg in db.messages:
            # If two DBCs define the same frame ID, the first one wins.
            messages_by_frame_id.setdefault(msg.frame_id, msg)
    return messages_by_frame_id


MESSAGES_BY_FRAME_ID = load_messages_by_frame_id(DBC_FILES)

# ── DBC parser ────────────────────────────────────────────────────────────────

def parse_dbc(path: str) -> dict:
    """
    Returns { can_id_int: { signal_name: (start_bit, length, little_endian,
                                          unsigned, scale, offset) } }
    Bit 31 in the DBC message ID means extended frame – we strip it for lookup.
    """
    messages = {}
    current_id = None

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()

            # BO_ 1794 NDCDCStatus: 8 DCDC
            m = re.match(r"^BO_\s+(\d+)\s+\w+\s*:\s*\d+", line)
            if m:
                raw_id = int(m.group(1))
                current_id = raw_id & 0x1FFFFFFF   # strip extended-flag bit
                messages[current_id] = {}
                continue

            # SG_ NDCDCState : 0|4@1+ (1,0) [0|15] "" SECU
            m = re.match(
                r"^SG_\s+(\w+)\s+(?:\w+\s*:\s*)?(\d+)\|(\d+)@([01])([+-])"
                r"\s*\(([-\d.]+),([-\d.]+)\)",
                line,
            )
            if m and current_id is not None:
                name       = m.group(1)
                start_bit  = int(m.group(2))
                length     = int(m.group(3))
                little_end = m.group(4) == "1"
                unsigned   = m.group(5) == "+"
                scale      = float(m.group(6))
                offset     = float(m.group(7))
                messages[current_id][name] = (
                    start_bit, length, little_end, unsigned, scale, offset
                )

    return messages


def extract_signal(data: bytes, start_bit: int, length: int,
                   little_endian: bool, unsigned: bool,
                   scale: float, offset: float) -> float:
    """Extract and scale a signal from a CAN frame's data bytes."""
    raw = 0
    if little_endian:
        for i in range(length):
            bit_pos = start_bit + i
            byte_i, bit_i = divmod(bit_pos, 8)
            if byte_i < len(data):
                raw |= ((data[byte_i] >> bit_i) & 1) << i
    else:  # big-endian (Motorola)
        bit = start_bit
        for i in range(length):
            byte_i, bit_i = divmod(bit, 8)
            if byte_i < len(data):
                raw |= ((data[byte_i] >> (7 - bit_i)) & 1) << (length - 1 - i)
            # advance to next Motorola bit
            if bit_i == 0:
                bit += 15
            else:
                bit -= 1

    if not unsigned:
        if raw & (1 << (length - 1)):
            raw -= 1 << length

    return raw * scale + offset


# ── Log parser ─────────────────────────────────────────────────────────────────

LOG_RE = re.compile(
    r"(\d+:\d+:\d+:\d+)\s+\w+\s+\d+\s+(0x[0-9A-Fa-f]+)\s+([sx])r?\s+(\d+)((?:\s+[0-9A-Fa-f]{2})*)"
)

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


def decode_frame(can_id: int, data: bytes) -> tuple[dict[str, float], list[dict]]:
    """
    Decode one CAN frame via cantools.
    Returns (decoded_signals, diagnostics).
    """
    msg = MESSAGES_BY_FRAME_ID.get(can_id)
    if msg is None:
        return {}, [{"type": "unknown_frame_id", "can_id": hex(can_id)}]

    diagnostics: list[dict] = []
    expected_len = getattr(msg, "length", None)
    if isinstance(expected_len, int) and expected_len > 0:
        if len(data) < expected_len:
            # Pad missing bytes so multiplexed decoding has stable bit locations.
            data = data + b"\x00" * (expected_len - len(data))
        elif len(data) > expected_len:
            data = data[:expected_len]

    try:
        raw_decoded = msg.decode(
            data,
            decode_choices=False,   # keep numbers (frontend expects numeric values)
            scaling=True,
            decode_containers=False,
            allow_truncated=True,
            allow_excess=True,
        )
    except Exception as e:
        diagnostics.append({"type": "decode_error", "can_id": hex(can_id), "error": str(e)})
        return {}, diagnostics

    decoded: dict[str, float] = {}
    for k, v in raw_decoded.items():
        if v is None:
            continue
        if isinstance(v, bool):
            decoded[k] = float(int(v))
        elif isinstance(v, (int, float)):
            decoded[k] = round(float(v), 4)
        # If a signal decodes into a container/string, skip it for now.

    return decoded, diagnostics


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


# ── WebSocket endpoint ─────────────────────────────────────────────────────────
#
# DBC_FILES / LOG_FILE are defined above using absolute paths.


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        prev_ts = None

        for ts_ms, can_id, data in iter_log_frames(LOG_FILE):
                # Replay at original speed
                if prev_ts is not None:
                    delta = (ts_ms - prev_ts) / 1000.0
                    if 0 < delta < 2.0:          # skip gaps > 2 s
                        await asyncio.sleep(delta)
                prev_ts = ts_ms

                decoded, diagnostics = decode_frame(can_id, data)
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