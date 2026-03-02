import json
import os
import logging
from typing import Optional

logger = logging.getLogger("MemoryManager")


class MemoryManager:
    """
    Handles memory-related services:
    - 0x23: Read Memory By Address
    - 0x35: Request Upload
    - 0x36: Transfer Data
    Now loads from the central ECU diagnostic definition file.
    """

    def __init__(self, config_path: str = "uds/config/ecu_diag.json") -> None:
        self.config_path = config_path
        self.memory_map = []
        self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    mem_config = config.get("memory", {})
                    for name, details in mem_config.items():
                        start = details["start"]
                        size = details["size"]
                        # Create a buffer for this region
                        buf = bytearray([0xFF if details["type"] == "FLASH" else 0x00] * size)
                        self.memory_map.append((start, start + size, buf, name))
        except Exception:
            # Fallback
            self.memory_map = [
                (0x08000000, 0x08000400, bytearray([0xFF] * 1024), "FLASH"),
                (0x20000000, 0x20000200, bytearray([0x00] * 512), "RAM"),
            ]

    def _resolve_address(self, address: int, size: int) -> tuple[Optional[bytearray], int]:
        """Convert a global address to a local memory object and offset."""
        for start, end, mem, name in self.memory_map:
            if start <= address < end:
                if address + size > end:
                    return None, 0  # Size goes out of bounds
                return mem, address - start
        return None, 0

    def read_memory(self, address: int, size: int) -> tuple[bool, bytes, int]:
        """Handle 0x23 - Read Memory By Address."""
        mem, offset = self._resolve_address(address, size)
        if mem is None:
            logger.warning(f"MEMORY: Read failed. Invalid address/size {hex(address)} + {size}")
            return False, b"", 0x31  # Request Out Of Range

        data = mem[offset : offset + size]
        logger.info(f"MEMORY: Read {size} bytes from {hex(address)}")
        return True, bytes(data), 0x00

    def request_upload(self, address: int, size: int) -> tuple[bool, bytes, int]:
        """Handle 0x35 - Request Upload."""
        mem, offset = self._resolve_address(address, size)
        if mem is None:
            return False, b"", 0x31  # Request Out Of Range

        logger.info(f"MEMORY: Upload Request for {size} bytes from {hex(address)}")
        # In a real ECU, we would prep a buffer here.
        # For simulation, we return Max Number of Block Length (0x20 0x02 0x00 -> 512 bytes)
        return True, b"\x20\x02\x00", 0x00

    def write_memory(self, address: int, size: int, data: bytes) -> tuple[bool, int]:
        """Helper for 0x34/0x36 sequence to write data to simulated memory."""
        mem, offset = self._resolve_address(address, size)
        if mem is None:
            return False, 0x31

        # For simplicity, we just write it all at once if the flow is correct.
        # In server.py we currently use a flash_buffer.
        # Here we just implement the direct memory access part.
        if len(data) > size:
            return False, 0x13  # Incorrect Length

        mem[offset : offset + len(data)] = data
        return True, 0x00
