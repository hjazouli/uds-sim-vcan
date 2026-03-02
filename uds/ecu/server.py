import os
import time
import logging
import threading
from typing import Dict, Optional

import struct
import can
import isotp
import udsoncan
from udsoncan.connections import IsoTPConnection
from udsoncan.client import Client
from udsoncan import services, Response
from udsoncan.ResponseCode import ResponseCode

from uds.ecu.did_store import DIDStore
from uds.ecu.dtc_store import DTCStore
from uds.ecu.security import SecurityManager
from uds.ecu.session_manager import SessionManager, DiagnosticSession
from uds.network.transport import create_connection, CHANNEL, USE_VIRTUAL

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ECUServer")


class ECUServer:
    """
    UDS ECU Server simulation.
    """

    def __init__(self, interface: str = CHANNEL, rxid: int = 0x7E0, txid: int = 0x7E8, bus: Optional[can.BusABC] = None) -> None:
        self.interface = interface
        self.rxid = rxid
        self.txid = txid

        self.did_store = DIDStore()
        self.dtc_store = DTCStore()
        self.security_manager = SecurityManager()
        self.session_manager = SessionManager(on_timeout=self._handle_session_timeout)

        # Service handlers mapping
        self.services = {
            services.DiagnosticSessionControl.request_id: self._handle_session_control,
            services.ECUReset.request_id: self._handle_ecu_reset,
            services.SecurityAccess.request_id: self._handle_security_access,
            services.ReadDataByIdentifier.request_id: self._handle_read_did,
            services.WriteDataByIdentifier.request_id: self._handle_write_did,
            services.ClearDiagnosticInformation.request_id: self._handle_clear_dtc,
            services.ReadDTCInformation.request_id: self._handle_read_dtc,
            services.TesterPresent.request_id: self._handle_tester_present,
            services.RoutineControl.request_id: self._handle_routine_control,
            services.RequestDownload.request_id: self._handle_request_download,
            services.TransferData.request_id: self._handle_transfer_data,
            services.RequestTransferExit.request_id: self._handle_request_transfer_exit,
        }

        # Flashing state variables
        self.transfer_active = False
        self.expected_seq_counter = 1
        self.flash_buffer = bytearray()

        # CAN bus and connection (OS-agnostic via transport factory)
        try:
            self.connection, self._transport_extras = create_connection(
                rxid=self.rxid,
                txid=self.txid,
                interface=self.interface,
                bus=bus
            )
        except Exception as e:
            logger.error(f"Failed to initialize transport: {e}")
            raise

        self.running = False

    def _handle_session_timeout(self) -> None:
        """Callback when session times out."""
        self.security_manager.reset()
        self.transfer_active = False
        self.flash_buffer = bytearray()

    def _handle_session_control(
        self, request: udsoncan.Request
    ) -> Response:
        """Handle 0x10 - DiagnosticSessionControl."""
        session_type = request.subfunction
        if session_type in [
            DiagnosticSession.DEFAULT,
            DiagnosticSession.PROGRAMMING,
            DiagnosticSession.EXTENDED,
        ]:
            self.session_manager.set_session(session_type)
            return Response(
                services.DiagnosticSessionControl,
                ResponseCode.PositiveResponse,
                data=bytes([session_type, 0x00, 0x32, 0x01, 0xF4]),
            )  # P2 and P2*
        return Response(services.DiagnosticSessionControl, ResponseCode.SubFunctionNotSupported)

    def _handle_ecu_reset(self, request: udsoncan.Request) -> Response:
        """Handle 0x11 - ECUReset."""
        if not (self.session_manager.is_extended or self.session_manager.is_programming):
            return Response(services.ECUReset, ResponseCode.ServiceNotSupportedInActiveSession)

        reset_type = request.subfunction
        if reset_type == 0x01:  # HardReset
            self.session_manager.reset()
            self.security_manager.reset()
            self.dtc_store.reset()
            self.transfer_active = False
            self.flash_buffer = bytearray()
            return Response(
                services.ECUReset, ResponseCode.PositiveResponse, data=bytes([reset_type])
            )
        elif reset_type == 0x03:  # SoftReset
            self.did_store.reset_to_defaults()
            return Response(
                services.ECUReset, ResponseCode.PositiveResponse, data=bytes([reset_type])
            )

        return Response(services.ECUReset, ResponseCode.SubFunctionNotSupported)

    def _handle_security_access(
        self, request: udsoncan.Request
    ) -> Response:
        """Handle 0x27 - SecurityAccess."""
        if not (self.session_manager.is_extended or self.session_manager.is_programming):
            return Response(
                services.SecurityAccess, ResponseCode.ServiceNotSupportedInActiveSession
            )

        subfunction = request.subfunction

        if subfunction == 0x01:  # RequestSeed
            if self.security_manager.lockout_active:
                return Response(services.SecurityAccess, ResponseCode.ExceedNumberOfAttempts)
            seed = self.security_manager.generate_seed()
            return Response(
                services.SecurityAccess,
                ResponseCode.PositiveResponse,
                data=bytes([subfunction]) + seed,
            )

        elif subfunction == 0x02:  # SendKey
            if self.security_manager.lockout_active:
                return Response(services.SecurityAccess, ResponseCode.ExceedNumberOfAttempts)

            if self.security_manager.validate_key(request.data):
                return Response(
                    services.SecurityAccess,
                    ResponseCode.PositiveResponse,
                    data=bytes([subfunction]),
                )
            else:
                # Even if it just reached MAX_ATTEMPTS, this specific error is InvalidKey.
                # Lockout will block the NEXT attempt.
                return Response(services.SecurityAccess, ResponseCode.InvalidKey)

        return Response(services.SecurityAccess, ResponseCode.SubFunctionNotSupported)

    def _handle_read_did(self, request: udsoncan.Request) -> Response:
        """Handle 0x22 - ReadDataByIdentifier."""
        payload = request.data
        if not payload or len(payload) % 2 != 0:
            return Response(services.ReadDataByIdentifier, ResponseCode.IncorrectMessageLengthOrInvalidFormat)
        
        dids = [struct.unpack(">H", payload[i:i+2])[0] for i in range(0, len(payload), 2)]
        response_data = b""
        for did in dids:
            try:
                val = self.did_store.read(did)
                response_data += struct.pack(">H", did) + val
            except KeyError:
                return Response(services.ReadDataByIdentifier, ResponseCode.RequestOutOfRange)

        return Response(
            services.ReadDataByIdentifier, ResponseCode.PositiveResponse, data=response_data
        )

    def _handle_write_did(self, request: udsoncan.Request) -> Response:
        """Handle 0x2E - WriteDataByIdentifier."""
        if self.security_manager.locked:
            return Response(services.WriteDataByIdentifier, ResponseCode.SecurityAccessDenied)

        payload = request.data
        if len(payload) < 2:
            return Response(services.WriteDataByIdentifier, ResponseCode.IncorrectMessageLengthOrInvalidFormat)
            
        did = struct.unpack(">H", payload[:2])[0]
        data = payload[2:]
        try:
            self.did_store.write(did, data)
            return Response(
                services.WriteDataByIdentifier,
                ResponseCode.PositiveResponse,
                data=struct.pack(">H", did),
            )
        except KeyError:
            return Response(services.WriteDataByIdentifier, ResponseCode.RequestOutOfRange)
        except PermissionError:
            return Response(services.WriteDataByIdentifier, ResponseCode.ConditionsNotCorrect)
        except ValueError:
            return Response(
                services.WriteDataByIdentifier, ResponseCode.IncorrectMessageLengthOrInvalidFormat
            )

    def _handle_clear_dtc(self, request: udsoncan.Request) -> Response:
        """Handle 0x14 - ClearDiagnosticInformation."""
        self.dtc_store.clear_dtcs()
        return Response(services.ClearDiagnosticInformation, ResponseCode.PositiveResponse)

    def _handle_read_dtc(self, request: udsoncan.Request) -> Response:
        """Handle 0x19 - ReadDTCInformation."""
        subfunction = request.subfunction
        if subfunction == 0x02:  # reportDTCByStatusMask
            if not request.data:
                return Response(services.ReadDTCInformation, ResponseCode.IncorrectMessageLengthOrInvalidFormat)
            mask = request.data[0]
            matching_dtcs = self.dtc_store.get_dtcs_by_status_mask(mask)

            # Protocol for 0x19 0x02: [SubFn] [StatusAvailabilityMask] [DTC1...][Status1] ...
            response_data = bytes([subfunction]) + b"\xff"
            for dtc in matching_dtcs:
                # DTC format in response is 3 bytes code + 1 byte status
                code_bytes = struct.pack(">I", dtc["code"])[1:]  # 3 bytes
                status_byte = struct.pack("B", dtc["status"])
                response_data += code_bytes + status_byte

            return Response(
                services.ReadDTCInformation, ResponseCode.PositiveResponse, data=response_data
            )

        return Response(services.ReadDTCInformation, ResponseCode.SubFunctionNotSupported)

    def _handle_tester_present(self, request: udsoncan.Request) -> Response:
        """Handle 0x3E - TesterPresent."""
        self.session_manager.reset_timer()
        return Response(
            services.TesterPresent, ResponseCode.PositiveResponse, data=bytes([request.subfunction])
        )

    def _handle_routine_control(self, request: udsoncan.Request) -> Response:
        """Handle 0x31 - RoutineControl."""
        if not self.session_manager.is_programming:
            return Response(services.RoutineControl, ResponseCode.ServiceNotSupportedInActiveSession)

        subfunction = request.subfunction
        if len(request.data) < 2:
            return Response(services.RoutineControl, ResponseCode.IncorrectMessageLengthOrInvalidFormat)
            
        routine_id = struct.unpack(">H", request.data[:2])[0]

        if routine_id == 0xFF00:  # Erase Memory
            if subfunction == services.RoutineControl.ControlType.startRoutine:
                logger.info("ROUTINE: Erasing Memory...")
                self.flash_buffer = bytearray()
                return Response(services.RoutineControl, ResponseCode.PositiveResponse, data=bytes([subfunction]) + struct.pack(">H", routine_id))
        
        elif routine_id == 0xFF01:  # Check Dependencies
            if subfunction == services.RoutineControl.ControlType.startRoutine:
                logger.info("ROUTINE: Checking Dependencies...")
                return Response(services.RoutineControl, ResponseCode.PositiveResponse, data=bytes([subfunction]) + struct.pack(">H", routine_id) + b"\x00") # Success

        return Response(services.RoutineControl, ResponseCode.RequestOutOfRange)

    def _handle_request_download(self, request: udsoncan.Request) -> Response:
        """Handle 0x34 - RequestDownload."""
        if not self.session_manager.is_programming:
            return Response(services.RequestDownload, ResponseCode.ServiceNotSupportedInActiveSession)

        if self.security_manager.locked:
            return Response(services.RequestDownload, ResponseCode.SecurityAccessDenied)

        # payload: [DFI] [ALFI] [Address...] [Size...]
        if len(request.data) < 2:
            return Response(services.RequestDownload, ResponseCode.IncorrectMessageLengthOrInvalidFormat)
            
        dfi = request.data[0]
        alfi = request.data[1]
        addr_len = (alfi >> 4) & 0x0F
        size_len = alfi & 0x0F
        
        if len(request.data) < 2 + addr_len + size_len:
             return Response(services.RequestDownload, ResponseCode.IncorrectMessageLengthOrInvalidFormat)
             
        addr_bytes = request.data[2 : 2 + addr_len]
        size_bytes = request.data[2 + addr_len : 2 + addr_len + size_len]
        
        address = int.from_bytes(addr_bytes, "big")
        size = int.from_bytes(size_bytes, "big")

        logger.info(f"DOWNLOAD: Request received. Address: {hex(address)}, Size: {size}")
        self.transfer_active = True
        self.expected_seq_counter = 1
        
        # Return Max Number of Block Length (Length Format Identifier = 0x20 -> 2 bytes)
        # We allow blocks up to 512 bytes for this simulation
        return Response(services.RequestDownload, ResponseCode.PositiveResponse, data=b"\x20\x02\x00")

    def _handle_transfer_data(self, request: udsoncan.Request) -> Response:
        """Handle 0x36 - TransferData."""
        if not self.transfer_active:
            return Response(services.TransferData, ResponseCode.RequestSequenceError)

        if not request.data:
            return Response(services.TransferData, ResponseCode.IncorrectMessageLengthOrInvalidFormat)
            
        seq_counter = request.data[0]
        data_payload = request.data[1:]
        
        if seq_counter != self.expected_seq_counter:
            logger.error(f"TRANSFER: Wrong sequence counter. Expected {self.expected_seq_counter}, got {seq_counter}")
            return Response(services.TransferData, ResponseCode.WrongBlockSequenceCounter)

        logger.info(f"TRANSFER: Received block {seq_counter} ({len(data_payload)} bytes)")
        self.flash_buffer.extend(data_payload)
        
        self.expected_seq_counter = (self.expected_seq_counter + 1) % 0x100
        return Response(services.TransferData, ResponseCode.PositiveResponse, data=bytes([seq_counter]))

    def _handle_request_transfer_exit(self, request: udsoncan.Request) -> Response:
        """Handle 0x37 - RequestTransferExit."""
        if not self.transfer_active:
            return Response(services.RequestTransferExit, ResponseCode.RequestSequenceError)

        logger.info(f"EXIT: Transfer complete. Total bytes: {len(self.flash_buffer)}")
        self.transfer_active = False
        return Response(services.RequestTransferExit, ResponseCode.PositiveResponse)

    def process_request(self, payload: bytes) -> None:
        """Decode and handle an incoming UDS request."""
        if not payload:
            return

        try:
            req = udsoncan.Request.from_payload(payload)
            logger.info(f"Received Request: {req}")

            if req.service.request_id in self.services:
                response = self.services[req.service.request_id](req)
            else:
                response = udsoncan.Response(req.service, ResponseCode.ServiceNotSupported)

            logger.info(f"Sending Response: {response}")
            self.connection.send(response.get_payload())

        except Exception as e:
            logger.error(f"Error processing request: {e}")

    def run(self) -> None:
        """Main loop for the server."""
        self.running = True
        logger.info(
            f"ECU Server started on {self.interface} (RX: 0x{self.rxid:03X}, TX: 0x{self.txid:03X})"
        )

        try:
            while self.running:
                # Check for session timeout
                self.session_manager.check_timeout()

                # Check for incoming requests
                payload = self.connection.wait_frame(timeout=0.1)
                if payload:
                    self.process_request(payload)

                time.sleep(0.01)
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Server error: {e}")

    def stop(self) -> None:
        """Stop the server."""
        self.running = False
        logger.info("ECU Server stopping...")
        if USE_VIRTUAL:
            # VirtualIsoTPConnection has its own close method
            if hasattr(self.connection, "close"):
                self.connection.close()
        else:
            if hasattr(self, "_transport_extras") and "socket" in self._transport_extras:
                self._transport_extras["socket"].close()


if __name__ == "__main__":
    server = ECUServer()
    server.run()
