import asyncio
import threading
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import can
from udsoncan import services

from uds.ecu.server import ECUServer
from uds.tester.client import UDSClient
from uds.network.transport import CHANNEL

from uds.tools.logging_config import setup_logging

# Configure logging using our premium central config
setup_logging()
logger = logging.getLogger("UDS-Web-API")

app = FastAPI(title="UDS Simulator Dashboard API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Shared State & Monitors ---


class ConnectionManager:
    """Manages active WebSockets for live CAN traffic."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()

# Global instances (to be initialized by the launcher)
ecu_server: Optional[ECUServer] = None
can_bus: Optional[can.BusABC] = None


def decode_uds_frame(msg: can.Message) -> Dict[str, Any]:
    """Helper to decode a CAN message for the UI."""
    data = msg.data
    ts = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S.%f")[:-3]
    direction = "RX" if msg.arbitration_id == 0x7E8 else "TX"

    # Very simple decoding for the UI
    service_name = "Unknown"
    sid = 0x00
    if len(data) > 1:
        pci = data[0]
        frame_type = (pci & 0xF0) >> 4
        if frame_type == 0:
            sid = data[1]
        elif frame_type == 1:
            sid = data[2]

        is_response = (sid & 0x40) != 0
        actual_sid = sid & ~0x40 if is_response else sid

        for name, entry in services.__dict__.items():
            if hasattr(entry, "request_id") and entry.request_id == actual_sid:
                service_name = name
                break

    return {
        "timestamp": ts,
        "id": f"0x{msg.arbitration_id:03X}",
        "direction": direction,
        "sid": f"0x{sid:02X}",
        "service": service_name,
        "data_hex": " ".join([f"{b:02X}" for b in data]),
    }


def background_monitor():
    """Threaded monitor that broadcasts to WebSockets."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # We use a shared virtual bus that both ECU and Monitor see
    bus = can.interface.Bus(channel=CHANNEL, interface="virtual")

    while True:
        msg = bus.recv(timeout=0.1)
        if msg:
            decoded = decode_uds_frame(msg)
            asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps(decoded)), loop)


# --- API Endpoints ---


class SessionRequest(BaseModel):
    session_type: int


@app.post("/api/ecu/session")
async def set_session(req: SessionRequest):
    """Trigger a session change using a client sequence."""
    try:
        with UDSClient() as client:
            resp = client.change_session(req.session_type)
            return {"status": "success", "response": str(resp.code_name)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ecu/status")
async def get_status():
    """Return the current mocked status of the ECU."""
    if not ecu_server:
        return {"status": "offline"}

    return {
        "status": "online",
        "session": "Extended" if ecu_server.session_manager.is_extended else "Default",
        "security": "Unlocked" if not ecu_server.security_manager.locked else "Locked",
        "dtc_count": len(ecu_server.dtc_store.dtcs),
    }


@app.post("/api/ecu/read_vin")
async def read_vin():
    """Shortcut to read the VIN."""
    try:
        with UDSClient() as client:
            resp = client.read_did(0xF190)
            return {
                "vin": resp.data.decode("ascii") if resp.data else "N/A",
                "status": resp.code_name,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ecu/live_data")
async def get_live_data():
    """Fetch specialized inverter metrics via a single combined UDS 0x22 request."""
    import struct

    try:
        with UDSClient() as client:
            # Combined read for efficiency: Voltage, Temp, Speed, Torque
            resp = client.read_did([0x4001, 0x4003, 0x4004, 0x4005])

            # Invert response mapping logic
            # response.service_data.values returns {DID: bytes_value}
            results = resp.service_data.values if resp and resp.service_data else {}

            data = {
                "voltage": struct.unpack(">H", results.get(0x4001, b"\x00\x00"))[0] / 10.0,
                "temperature": struct.unpack("B", results.get(0x4003, b"\x00"))[0],
                "speed": struct.unpack(">H", results.get(0x4004, b"\x00\x00"))[0],
                "torque": struct.unpack(">H", results.get(0x4005, b"\x00\x00"))[0],
            }
            return data
    except Exception as e:
        logger.debug(f"Live data fetch silent error: {e}")
        return {"voltage": 0, "temperature": 0, "speed": 0, "torque": 0}


class RoutineRequest(BaseModel):
    routine_id: int


@app.post("/api/ecu/routine")
async def trigger_routine(req: RoutineRequest):
    """Trigger a UDS Routine Control (0x31) by ID."""
    try:
        with UDSClient() as client:
            resp = client.start_routine(req.routine_id)
            return {"status": resp.code_name, "raw_data": resp.data.hex() if resp.data else ""}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ecu/reset")
async def ecu_reset(req: Dict[str, int]):
    """Service 0x11 - ECU Reset."""
    try:
        with UDSClient() as client:
            resp = client.ecu_reset(req.get("reset_type", 1))
            return {"status": resp.code_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ecu/clear_dtcs")
async def clear_dtcs():
    """Service 0x14 - Clear DTCs."""
    try:
        with UDSClient() as client:
            resp = client.clear_dtcs()
            return {"status": resp.code_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ecu/unlock")
async def unlock_security():
    """Service 0x27 - Security Access (Automated Unlock)."""
    try:
        with UDSClient() as client:
            seed = client.request_seed(1)
            seed_int = int.from_bytes(seed, "big")
            key_int = seed_int ^ 0xDEADBEEF
            resp = client.send_key(1, key_int)
            return {"status": resp.code_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ecu/memory_dump")
async def memory_dump():
    """Service 0x23 - Read Memory Snapshot (8 bytes from FLASH)."""
    import udsoncan

    try:
        with UDSClient() as client:
            loc = udsoncan.MemoryLocation(
                address=0x08000000, memorysize=8, address_format=32, memorysize_format=8
            )
            resp = client.read_memory(loc)
            return {"data": resp.data.hex() if resp.data else "", "status": resp.code_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ecu/comm_control")
async def comm_control(req: Dict[str, int]):
    """Service 0x28 - Communication Control."""
    try:
        with UDSClient() as client:
            resp = client.communication_control(req.get("control_type", 0x00), 0x01)
            return {"status": resp.code_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/traffic")
async def websocket_traffic(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    # Start the monitor thread
    t = threading.Thread(target=background_monitor, daemon=True)
    t.start()
    logger.info("Background CAN monitor thread started")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
