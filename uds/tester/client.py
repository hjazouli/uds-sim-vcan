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

from uds.tools.logging_config import setup_logging

# Use the central logging config
setup_logging()
logger = logging.getLogger("UDSClient")

import json
import os
from udsoncan.common.DidCodec import AsciiCodec

def get_config_from_json(path="uds/config/ecu_diag.json"):
    """Load DIDs from JSON and build udsoncan config."""
    config = {
        "data_identifiers": {},
        "use_server_timing_control": True
    }
    
    if not os.path.exists(path):
        return config

    try:
        with open(path, 'r') as f:
            data = json.load(f)
            for did in data.get("dids", []):
                did_id = int(did["id"], 16) if isinstance(did["id"], str) else did["id"]
                dtype = did.get("type", "ASCII")
                size = did.get("size", 1)
                
                if dtype == "ASCII":
                    config["data_identifiers"][did_id] = AsciiCodec(size)
                elif dtype == "UINT16":
                    config["data_identifiers"][did_id] = ">H"
                elif dtype == "UINT8":
                    config["data_identifiers"][did_id] = "B"
                else:
                    config["data_identifiers"][did_id] = "B" * size
    except Exception as e:
        logger.error(f"Failed to load DID config: {e}")
        
    config["data_identifiers"][0xFFFF] = "B"
    return config

# Shared config will be initialized in the class to allow for dynamic reloading


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
        config = get_config_from_json()
        self.client = Client(self.connection, config=config)
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

    def read_did(self, did: Union[int, List[int]]) -> udsoncan.Response:
        """Read one or more data identifiers."""
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

    def stop_routine(self, routine_id: int) -> udsoncan.Response:
        """Routine control - stop routine."""
        if self.client:
            try:
                return self.client.routine_control(
                    routine_id, udsoncan.services.RoutineControl.ControlType.stopRoutine
                )
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.RoutineControl, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def request_routine_results(self, routine_id: int) -> udsoncan.Response:
        """Routine control - request routine results."""
        if self.client:
            try:
                return self.client.routine_control(
                    routine_id, udsoncan.services.RoutineControl.ControlType.requestRoutineResults
                )
            except Exception as e:
                return getattr(
                    e,
                    "response",
                    udsoncan.Response(services.RoutineControl, ResponseCode.GeneralReject),
                )
        raise RuntimeError("Client not opened")

    def read_memory(self, memory_location: udsoncan.MemoryLocation) -> udsoncan.Response:
        """Service 0x23 - Read Memory By Address."""
        if self.client:
            try:
                return self.client.read_memory_by_address(memory_location)
            except Exception as e:
                return getattr(e, "response", udsoncan.Response(services.ReadMemoryByAddress, ResponseCode.GeneralReject))
        raise RuntimeError("Client not opened")

    def communication_control(self, control_type: int, communication_type: int) -> udsoncan.Response:
        """Service 0x28 - Communication Control."""
        if self.client:
            try:
                return self.client.communication_control(control_type, communication_type)
            except Exception as e:
                return getattr(e, "response", udsoncan.Response(services.CommunicationControl, ResponseCode.GeneralReject))
        raise RuntimeError("Client not opened")

    def io_control(self, did: int, control_param: int, values: Optional[Union[dict, bytes]] = None) -> udsoncan.Response:
        """Service 0x2F - Input Output Control By Identifier."""
        if self.client:
            try:
                return self.client.io_control(did, control_param, values)
            except Exception as e:
                return getattr(e, "response", udsoncan.Response(services.InputOutputControlByIdentifier, ResponseCode.GeneralReject))
        raise RuntimeError("Client not opened")

    def request_upload(self, memory_location: udsoncan.MemoryLocation) -> udsoncan.Response:
        """Service 0x35 - Request Upload."""
        if self.client:
            try:
                return self.client.request_upload(memory_location)
            except Exception as e:
                return getattr(e, "response", udsoncan.Response(services.RequestUpload, ResponseCode.GeneralReject))
        raise RuntimeError("Client not opened")

    def request_file_transfer(self, mode: int, path: str) -> udsoncan.Response:
        """Service 0x38 - Request File Transfer."""
        if self.client:
            try:
                return self.client.request_file_transfer(mode, path)
            except Exception as e:
                return getattr(e, "response", udsoncan.Response(services.RequestFileTransfer, ResponseCode.GeneralReject))
        raise RuntimeError("Client not opened")
