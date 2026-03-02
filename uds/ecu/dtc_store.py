import json
import os
from typing import List, Dict, Optional

class DTCStore:
    """
    Simulated DTC database (Diagnostic Trouble Codes).
    Now loads from the central ECU diagnostic definition file.
    """

    def __init__(self, config_path: str = "uds/config/ecu_diag.json") -> None:
        self.config_path = config_path
        self._initial_dtcs = []
        self._load_config()
        self.dtcs = list(self._initial_dtcs)

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    raw_dtcs = config.get("dtcs", [])
                    self._initial_dtcs = []
                    for d in raw_dtcs:
                        code = int(d["code"], 16) if isinstance(d["code"], str) else d["code"]
                        self._initial_dtcs.append({
                            "code": code,
                            "status": d.get("status", 0x01),
                            "name": d.get("name", "Unknown DTC")
                        })
        except Exception:
            # Fallback to defaults if file is missing
            self._initial_dtcs = [
                {"code": 0x0100, "status": 0x01, "name": "P0100"},
                {"code": 0xC100, "status": 0x04, "name": "U0100"},
                {"code": 0x4035, "status": 0x08, "name": "C0035"},
            ]

    def get_dtcs_by_status_mask(self, mask: int) -> List[Dict]:
        """Return DTCs matching the status mask (Service 0x19 0x02)."""
        return [dtc for dtc in self.dtcs if (dtc["status"] & mask) != 0]

    def count_dtcs_by_status_mask(self, mask: int) -> int:
        """Return count for reportNumberOfDTCByStatusMask (Service 0x19 0x01)."""
        return len(self.get_dtcs_by_status_mask(mask))

    def clear_dtcs(self) -> None:
        """Clear all stored DTCs."""
        self.dtcs = []

    def reset(self) -> None:
        """Restore initial DTCs."""
        self.dtcs = list(self._initial_dtcs)
