import logging
import time
from typing import List, Optional, Union

import can
import isotp
import udsoncan
from udsoncan.connections import IsoTPConnection
from udsoncan.client import Client
from udsoncan import services
from udsoncan.ResponseCode import ResponseCode

from uds.network.transport import create_connection, CHANNEL, USE_VIRTUAL

from udsoncan.common.DidCodec import AsciiCodec

logger = logging.getLogger("UDSClient")

# Default DID configuration for clear text / simple types
DEFAULT_CONFIG = {
    "data_identifiers": {
        0xF190: AsciiCodec(17),
        0xF18C: AsciiCodec(8),
        0xF187: ">H",
        0xF40D: "B",
        0xD001: ">H",
        0xD002: "B",
        0xDDDD: "B",
        0xFFFF: "B",
    },
    "use_server_timing_control": True,
}


class UDSClient:
    """
    Wrapper for udsoncan Client to simplify test sequences.
    Works on Linux (SocketCAN), macOS, and Windows (virtual bus).
    """

    def __init__(
        self,
        interface: str = CHANNEL,
        txid: int = 0x7E0,
        rxid: int = 0x7E8,
        bus: Optional[can.BusABC] = None,
    ) -> None:
        self.interface = interface
        self.txid = txid
        self.rxid = rxid

        try:
            # Client TX → Server RX (0x7E0), Client RX ← Server TX (0x7E8)
            self.connection, self._transport_extras = create_connection(
                rxid=self.rxid, txid=self.txid, interface=self.interface, bus=bus
            )
        except Exception as e:
            logger.error(f"Failed to initialize transport for client: {e}")
            raise

        self.client: Optional[Client] = None

    def __enter__(self) -> "UDSClient":
        self.client = Client(self.connection, config=DEFAULT_CONFIG)
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
            try:
                return self.client.change_session(session)
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(
                        services.DiagnosticSessionControl, ResponseCode.GeneralReject
                    ),
                )
        raise RuntimeError("Client not opened")

    def request_seed(self, level: int = 1) -> bytes:
        """Request security seed."""
        if self.client:
            try:
                response = self.client.request_seed(level)
                return response.data
            except Exception as e:
                resp = getattr(e, "response", None)
                return resp.data if resp and hasattr(resp, "data") else b""
        raise RuntimeError("Client not opened")

    def send_key(self, level: int, key: Union[bytes, int]) -> udsoncan.Response:
        """Send security key."""
        if self.client:
            if isinstance(key, int):
                key = key.to_bytes(4, "big")
            try:
                return self.client.send_key(level + 1, key)
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.SecurityAccess, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def read_did(self, did: int) -> udsoncan.Response:
        """Read data by identifier."""
        if self.client:
            try:
                return self.client.read_data_by_identifier(did)
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.ReadDataByIdentifier, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def write_did(self, did: int, data: Union[bytes, int, str]) -> udsoncan.Response:
        """Write data by identifier."""
        if self.client:
            if isinstance(data, int):
                data = data.to_bytes(2, "big")
            try:
                return self.client.write_data_by_identifier(did, data)
            except Exception as e:
                # If it's a codec error (e.g. wrong length), map it to NRC 0x13
                if isinstance(e, ValueError) and (
                    "length" in str(e).lower() or "string must be" in str(e).lower()
                ):
                    return udsoncan.Response(
                        services.WriteDataByIdentifier,
                        ResponseCode.IncorrectMessageLengthOrInvalidFormat,
                    )
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.WriteDataByIdentifier, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def read_dtcs(self, mask: int = 0xFF) -> udsoncan.Response:
        """Read DTCs by status mask."""
        if self.client:
            try:
                return self.client.get_dtc_by_status_mask(mask)
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.ReadDTCInformation, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def clear_dtcs(self, group: int = 0xFFFFFF) -> udsoncan.Response:
        """Clear diagnostic information."""
        if self.client:
            try:
                return self.client.clear_dtc(group)
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(
                        services.ClearDiagnosticInformation, ResponseCode.GeneralReject
                    ),
                )
        raise RuntimeError("Client not opened")

    def ecu_reset(self, level: int) -> udsoncan.Response:
        """Send ECU reset."""
        if self.client:
            try:
                return self.client.ecu_reset(level)
            except Exception as e:
                return getattr(
                    e, "response", udsoncan.Response(services.ECUReset, ResponseCode.GeneralReject)
                )
        raise RuntimeError("Client not opened")

    def request_download(self, memory_location: udsoncan.MemoryLocation) -> udsoncan.Response:
        """Request download service."""
        if self.client:
            try:
                return self.client.request_download(memory_location)
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.RequestDownload, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def transfer_data(self, sequence_counter: int, data: bytes) -> udsoncan.Response:
        """Transfer data service."""
        if self.client:
            try:
                return self.client.transfer_data(sequence_counter, data)
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.TransferData, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def request_transfer_exit(self) -> udsoncan.Response:
        """Request transfer exit service."""
        if self.client:
            try:
                return self.client.request_transfer_exit()
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.RequestTransferExit, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def start_routine(self, routine_id: int, data: bytes = b"") -> udsoncan.Response:
        """Routine control - start routine."""
        if self.client:
            try:
                return self.client.routine_control(
                    routine_id, udsoncan.services.RoutineControl.ControlType.startRoutine, data
                )
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.RoutineControl, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")
