import logging
from enum import IntEnum
from typing import Dict, Any, Optional

logger = logging.getLogger("IOControl")

class IOCtrlType(IntEnum):
    RETURN_CONTROL_TO_ECU = 0x00
    RESET_TO_DEFAULT = 0x01
    FREEZE_CURRENT_STATE = 0x02
    SHORT_TERM_ADJUSTMENT = 0x03

import json
import os

class IOControlManager:
    """
    Handles Service 0x2F - Input Output Control by Identifier.
    Simulates overriding ECU pins/signals like Fan, Lights, or Fuel Pump.
    Now loads from the central ECU diagnostic definition file.
    """
    
    def __init__(self, config_path: str = "uds/config/ecu_diag.json") -> None:
        self.config_path = config_path
        self.io_states = {}
        self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    raw_io = config.get("io_controls", [])
                    for io in raw_io:
                        did = int(io["id"], 16) if isinstance(io["id"], str) else io["id"]
                        self.io_states[did] = {
                            "name": io.get("name", "Unknown Actuator"),
                            "value": b"\x00",
                            "overridden": False
                        }
        except Exception:
            # Fallback
            self.io_states = {
                0x0101: {"name": "Engine Cooling Fan", "value": b"\x00", "overridden": False},
            }

    def handle_io_control(self, did: int, ctrl_type: int, control_params: bytes = b"") -> tuple[bool, bytes, int]:
        """
        Process the IO control request.
        Returns: (success_bool, response_data, nrc)
        """
        if did not in self.io_states:
            return False, b"", 0x31 # Request Out Of Range
            
        io = self.io_states[did]
        
        try:
            ctrl = IOCtrlType(ctrl_type)
        except ValueError:
            return False, b"", 0x12 # Subfunction Not Supported

        if ctrl == IOCtrlType.RETURN_CONTROL_TO_ECU:
            logger.info(f"IOCBI: Returning {io['name']} to ECU control")
            io["overridden"] = False
            
        elif ctrl == IOCtrlType.RESET_TO_DEFAULT:
            logger.info(f"IOCBI: Resetting {io['name']} to default")
            io["overridden"] = True
            io["value"] = b"\x00"
            
        elif ctrl == IOCtrlType.FREEZE_CURRENT_STATE:
            logger.info(f"IOCBI: Freezing {io['name']} state")
            io["overridden"] = True
            
        elif ctrl == IOCtrlType.SHORT_TERM_ADJUSTMENT:
            if not control_params:
                return False, b"", 0x13 # Incorrect Message Length
            logger.info(f"IOCBI: Adjusting {io['name']} to {control_params.hex()}")
            io["overridden"] = True
            io["value"] = control_params

        # Response format: [Subfunction] [Optional Status/Value Data]
        # In this sim, we return the subfunction followed by the current state/value data
        return True, bytes([ctrl_type]) + io["value"], 0x00

    def reset(self) -> None:
        """Reset all IO to ECU control."""
        for io in self.io_states.values():
            io["overridden"] = False
            io["value"] = b"\x00"
