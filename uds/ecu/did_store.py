import json
import os
import struct
from typing import Dict, Any, Union

class DIDStore:
    """
    Registry for Data Identifiers (DIDs).
    Loads from the central diagnostic definition file.
    """

    def __init__(self, config_path: str = "uds/config/ecu_diag.json") -> None:
        self.config_path = config_path
        self._dids_config = []
        self._dids: Dict[int, Any] = {}
        self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self._dids_config = config.get("dids", [])
                    for d in self._dids_config:
                        did_id = int(d["id"], 16) if isinstance(d["id"], str) else d["id"]
                        self._dids[did_id] = d["value"]
        except Exception:
            # Fallback
            self._dids = {
                0xF190: "WBA12345678901234",
                0xF18C: "ECU12345",
                0xF187: 120,
            }

    def read(self, did: int) -> bytes:
        """Read DID value and return as bytes."""
        if did not in self._dids:
            raise KeyError(f"DID 0x{did:04X} not found")

        val = self._dids[did]
        
        # Determine type from config if possible
        dtype = "ASCII"
        for d in self._dids_config:
            did_id = int(d["id"], 16) if isinstance(d["id"], str) else d["id"]
            if did_id == did:
                dtype = d.get("type", "ASCII")
                break

        if dtype == "ASCII":
            return val.encode('ascii') if isinstance(val, str) else bytes(val)
        elif dtype == "UINT16":
            return struct.pack(">H", val)
        elif dtype == "UINT8":
            return struct.pack("B", val)
            
        return b""

    def write(self, did: int, data: bytes) -> None:
        """Write DID value with length validation."""
        if did not in self._dids:
            raise KeyError(f"DID 0x{did:04X} not found")
            
        # Find expected size from config
        expected_size = None
        for d in self._dids_config:
            did_id = int(d["id"], 16) if isinstance(d["id"], str) else d["id"]
            if did_id == did:
                expected_size = d.get("size")
                break
        
        if expected_size is not None and len(data) != expected_size:
            raise ValueError(f"Invalid data length for DID 0x{did:04X}: expected {expected_size}, got {len(data)}")

        if did == 0xF190: # VIN
            self._dids[did] = data.decode('ascii')
        else:
            self._dids[did] = data # Store raw for others
            
    def reset_to_defaults(self) -> None:
        """Reinitialize DIDs."""
        self._load_config()
