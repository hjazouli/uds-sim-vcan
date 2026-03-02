import logging
import struct
from enum import IntEnum
from typing import Dict, Any, Optional

logger = logging.getLogger("RoutineStore")


class RoutineStatus(IntEnum):
    INACTIVE = 0x00
    RUNNING = 0x01
    COMPLETED_SUCCESS = 0x02
    COMPLETED_ERROR = 0x03
    STOPPED = 0x04


import json
import os


class RoutineStore:
    """
    Manages UDS Routine IDs (RID - Service 0x31) and their states.
    Now loads from the central ECU diagnostic definition file.
    """

    def __init__(self, config_path: str = "uds/config/ecu_diag.json") -> None:
        self.config_path = config_path
        self.routines = {}
        self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    raw_routines = config.get("routines", [])
                    for r in raw_routines:
                        rid = int(r["id"], 16) if isinstance(r["id"], str) else r["id"]
                        self.routines[rid] = {
                            "name": r.get("name", "Unknown Routine"),
                            "status": RoutineStatus.INACTIVE,
                            "results": b"\x00",
                            "sessions": r.get("sessions", [0x01, 0x02, 0x03]),
                        }
        except Exception:
            # Fallback
            self.routines = {
                0xFF00: {
                    "name": "Erase Memory",
                    "status": RoutineStatus.INACTIVE,
                    "results": b"\x00",
                    "sessions": [0x02],
                },
                0xFF01: {
                    "name": "Check Dependencies",
                    "status": RoutineStatus.INACTIVE,
                    "results": b"\x01",
                    "sessions": [0x02, 0x03],
                },
            }

    def start_routine(
        self, rid: int, current_session: int, params: bytes = b""
    ) -> tuple[bool, bytes, int]:
        """
        Attempt to start a routine.
        Returns: (success_bool, response_data, nrc)
        """
        if rid not in self.routines:
            return False, b"", 0x31  # Request Out Of Range

        routine = self.routines[rid]

        # Session check
        if current_session not in routine["sessions"]:
            return False, b"", 0x7E  # Subfunction Not Supported In Active Session

        logger.info(f"ROUTINE: Starting {routine['name']} (0x{rid:04X})")
        routine["status"] = RoutineStatus.RUNNING

        # Logic simulation
        if rid == 0xFF00:
            routine["status"] = RoutineStatus.COMPLETED_SUCCESS
            routine["results"] = b"\x00"
        elif rid == 0x0203:
            routine["results"] = b"\x00\x01"  # Running test

        # Response for 0x31 0x01: [RID High] [RID Low] [Optional Info]
        return True, struct.pack(">H", rid) + bytes([routine["status"]]), 0x00

    def stop_routine(self, rid: int, current_session: int) -> tuple[bool, bytes, int]:
        """Attempt to stop a routine."""
        if rid not in self.routines:
            return False, b"", 0x31

        routine = self.routines[rid]
        if routine["status"] != RoutineStatus.RUNNING:
            return False, b"", 0x24  # Request Sequence Error

        logger.info(f"ROUTINE: Stopping {routine['name']} (0x{rid:04X})")
        routine["status"] = RoutineStatus.STOPPED
        return True, struct.pack(">H", rid) + bytes([routine["status"]]), 0x00

    def get_results(self, rid: int, current_session: int) -> tuple[bool, bytes, int]:
        """Request results for a routine."""
        if rid not in self.routines:
            return False, b"", 0x31

        routine = self.routines[rid]
        logger.info(f"ROUTINE: Returning results for {routine['name']}")

        # Response for 0x31 0x03: [RID High] [RID Low] [Status] [Results...]
        return True, struct.pack(">H", rid) + bytes([routine["status"]]) + routine["results"], 0x00

    def reset(self) -> None:
        """Reset all routines to inactive."""
        for r in self.routines.values():
            r["status"] = RoutineStatus.INACTIVE
            r["results"] = b"\x00" if "results" in r else b""
