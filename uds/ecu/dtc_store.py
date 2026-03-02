from typing import List, Dict


class DTCStore:
    """
    Simulated DTC database (Diagnostic Trouble Codes).
    """

    def __init__(self) -> None:
        # Pre-seeded DTCs
        # P0100 - Mass Air Flow Sensor Fault (Active: 0x01)
        # U0100 - Lost Communication with ECM (Pending: 0x04)
        # C0035 - Brake Pressure Sensor Circuit (Stored: 0x08)
        self._initial_dtcs = [
            {"code": 0x0100, "status": 0x01, "name": "P0100"},
            {"code": 0xC100, "status": 0x04, "name": "U0100"},  # U0100 is 0xC100 (U=11 hex)
            {"code": 0x4035, "status": 0x08, "name": "C0035"},  # C0035 is 0x4035 (C=01 hex)
        ]
        self.dtcs = list(self._initial_dtcs)

    def get_dtcs_by_status_mask(self, mask: int) -> List[Dict]:
        """Return DTCs matching the status mask."""
        return [dtc for dtc in self.dtcs if (dtc["status"] & mask) != 0]

    def clear_dtcs(self) -> None:
        """Clear all stored DTCs."""
        self.dtcs = []

    def reset(self) -> None:
        """Restore initial DTCs (Hard Reset behavior)."""
        self.dtcs = list(self._initial_dtcs)
