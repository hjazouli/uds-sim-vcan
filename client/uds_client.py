import logging
import time
from typing import List, Optional, Union

import can
import isotp
import udsoncan
from udsoncan.connections import IsoTPConnection
from udsoncan.client import Client
from udsoncan import services

from server.transport import create_connection, CHANNEL, USE_VIRTUAL

logger = logging.getLogger("UDSClient")


class UDSClient:
    """
    Wrapper for udsoncan Client to simplify test sequences.
    Works on Linux (SocketCAN), macOS, and Windows (virtual bus).
    """

    def __init__(self, interface: str = CHANNEL, txid: int = 0x7E0, rxid: int = 0x7E8) -> None:
        self.interface = interface
        self.txid = txid
        self.rxid = rxid

        try:
            # Client TX → Server RX (0x7E0), Client RX ← Server TX (0x7E8)
            self.connection, self._transport_extras = create_connection(
                rxid=self.rxid,
                txid=self.txid,
                interface=self.interface,
            )
        except Exception as e:
            logger.error(f"Failed to initialize transport for client: {e}")
            raise

        self.client: Optional[Client] = None

    def __enter__(self) -> "UDSClient":
        self.client = Client(self.connection)
        self.client.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.client:
            self.client.close()
        if USE_VIRTUAL:
            if hasattr(self.connection, "close"):
                self.connection.close()
        else:
            if "socket" in self._transport_extras:
                self._transport_extras["socket"].close()

    def send_tester_present(self) -> None:
        """Send TesterPresent (0x3E) subfunction 0x00."""
        if self.client:
            self.client.tester_present()

    def change_session(self, session: int) -> udsoncan.Response:
        """Change diagnostic session."""
        if self.client:
            return self.client.change_session(session)
        raise RuntimeError("Client not opened")

    def request_seed(self, level: int = 1) -> bytes:
        """Request security seed."""
        if self.client:
            response = self.client.security_access(level)
            return response.data
        raise RuntimeError("Client not opened")

    def send_key(self, level: int, key: int) -> udsoncan.Response:
        """Send security key."""
        if self.client:
            return self.client.security_access(level + 1, key)
        raise RuntimeError("Client not opened")

    def read_did(self, did: int) -> udsoncan.Response:
        """Read data by identifier."""
        if self.client:
            return self.client.read_data_by_identifier(did)
        raise RuntimeError("Client not opened")

    def write_did(self, did: int, data: Union[bytes, int, str]) -> udsoncan.Response:
        """Write data by identifier."""
        if self.client:
            # udsoncan expects a dict or object for codec,
            # but for simple bytes we can just pass them if we don't use a full DID definition.
            # Here we wrap it in a bytes object if it's not already.
            if isinstance(data, str):
                data = data.encode("ascii")
            elif isinstance(data, int):
                # Guessing 2 bytes big endian based on our DIDs
                data = data.to_bytes(2, "big")

            return self.client.write_data_by_identifier(did, data)
        raise RuntimeError("Client not opened")

    def read_dtcs(self, mask: int = 0xFF) -> udsoncan.Response:
        """Read DTCs by status mask."""
        if self.client:
            return self.client.get_dtc_by_status_mask(mask)
        raise RuntimeError("Client not opened")

    def clear_dtcs(self) -> udsoncan.Response:
        """Clear diagnostic information."""
        if self.client:
            return self.client.clear_diagnostic_information(0xFFFFFF)
        raise RuntimeError("Client not opened")

    def ecu_reset(self, level: int) -> udsoncan.Response:
        """Send ECU reset."""
        if self.client:
            return self.client.ecu_reset(level)
        raise RuntimeError("Client not opened")

    def request_download(self, memory_location: udsoncan.MemoryLocation) -> udsoncan.Response:
        """Request download service."""
        if self.client:
            return self.client.request_download(memory_location)
        raise RuntimeError("Client not opened")

    def transfer_data(self, sequence_counter: int, data: bytes) -> udsoncan.Response:
        """Transfer data service."""
        if self.client:
            return self.client.transfer_data(sequence_counter, data)
        raise RuntimeError("Client not opened")

    def request_transfer_exit(self) -> udsoncan.Response:
        """Request transfer exit service."""
        if self.client:
            return self.client.request_transfer_exit()
        raise RuntimeError("Client not opened")

    def start_routine(self, routine_id: int, data: bytes = b"") -> udsoncan.Response:
        """Routine control - start routine."""
        if self.client:
            return self.client.routine_control(routine_id, udsoncan.services.RoutineControl.ControlType.startRoutine, data)
        raise RuntimeError("Client not opened")
