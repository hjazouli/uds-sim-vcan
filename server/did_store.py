from typing import Dict, Any, Union
import struct


class DIDStore:
    """
    Registry for Data Identifiers (DIDs).
    Handles reading and writing of simulated ECU parameters.
    """

    def __init__(self) -> None:
        # Default values for DIDs
        self._dids: Dict[int, Any] = {
            0xF190: b"WBA12345678901234",  # VIN (17 bytes)
            0xF18C: b"ECU12345",  # ECU Serial Number (8 bytes)
            0xF187: 120,  # Vehicle Speed (uint16, km/h)
            0xF40D: 0x01,  # Engine Status (1 byte: 0x01=Running)
            0xD001: 2500,  # Brake Torque Request (uint16, Nm)
            0xD002: 0x00,  # System State (1 byte: 0=Normal)
        }

    def read(self, did: int) -> bytes:
        """Read DID value and return as bytes."""
        if did not in self._dids:
            raise KeyError(f"DID 0x{did:04X} not found")

        val = self._dids[did]

        if did == 0xF190:  # VIN
            return val
        elif did == 0xF18C:  # Serial
            return val
        elif did == 0xF187:  # Speed
            return struct.pack(">H", val)
        elif did == 0xF40D:  # Engine Status
            return struct.pack("B", val)
        elif did == 0xD001:  # Brake Torque
            return struct.pack(">H", val)
        elif did == 0xD002:  # System State
            return struct.pack("B", val)

        return b""

    def write(self, did: int, data: bytes) -> None:
        """Write DID value from bytes."""
        if did not in self._dids:
            raise KeyError(f"DID 0x{did:04X} not found")

        if did == 0xF190:  # VIN
            if len(data) != 17:
                raise ValueError("VIN must be 17 bytes")
            self._dids[did] = data
        elif did == 0xD001:  # Brake Torque
            if len(data) != 2:
                raise ValueError("Brake Torque must be 2 bytes")
            self._dids[did] = struct.unpack(">H", data)[0]
        else:
            raise PermissionError(f"DID 0x{did:04X} is read-only")

    def reset_to_defaults(self) -> None:
        """Reinitialize DIDs to defaults (Soft Reset behavior)."""
        self._dids[0xF187] = 120
        self._dids[0xF40D] = 0x01
        self._dids[0xD001] = 2500
        self._dids[0xD002] = 0x00
        # Serial and VIN usually persist through soft reset in real ECUs,
        # but the spec says "reinitialize DIDs to defaults" for SoftReset.
        # I'll keep Serial/VIN but reset the dynamic ones.
