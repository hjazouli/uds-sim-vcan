"""
test_ecu_server.py — Unit tests for ECUServer handler logic.

The fixture mocks the transport layer so no vcan0 or virtual bus is required.
These tests run on any OS (macOS, Windows, Linux) in CI without CAN hardware.
"""

import pytest
from unittest.mock import MagicMock, patch
import udsoncan
from udsoncan import Response
from uds.ecu.server import ECUServer
from uds.ecu.session_manager import DiagnosticSession
import struct


@pytest.fixture
def server():
    """
    Provide an ECUServer instance with the transport layer fully mocked.
    This allows testing all handler logic without needing vcan0 or a virtual bus.
    """
    mock_conn = MagicMock()

    with patch("uds.network.transport.create_connection", return_value=(mock_conn, {})):
        s = ECUServer()

    return s


def test_ecu_server_initialization(server):
    assert server.rxid == 0x7E0
    assert server.txid == 0x7E8
    assert server.session_manager.current_session == DiagnosticSession.DEFAULT


def test_handle_session_control(server):
    # Test valid session transition
    request = udsoncan.Request(udsoncan.services.DiagnosticSessionControl, subfunction=0x03)
    response = server._handle_session_control(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    assert server.session_manager.current_session == DiagnosticSession.EXTENDED

    # Test invalid subfunction
    request = udsoncan.Request(udsoncan.services.DiagnosticSessionControl, subfunction=0x99)
    response = server._handle_session_control(request)
    assert response.code == udsoncan.Response.Code.SubFunctionNotSupported


def test_handle_read_did(server):
    # Test reading VIN (0xF190)
    request = udsoncan.Request(
        udsoncan.services.ReadDataByIdentifier, data=struct.pack(">H", 0xF190)
    )
    response = server._handle_read_did(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    assert b"WBA12345678901234" in response.data

    # Test reading non-existent DID
    request = udsoncan.Request(
        udsoncan.services.ReadDataByIdentifier, data=struct.pack(">H", 0xFFFF)
    )
    response = server._handle_read_did(request)
    assert response.code == udsoncan.Response.Code.RequestOutOfRange


def test_handle_security_access_flow(server):
    # SecurityAccess requires Extended or Programming session
    server.session_manager.set_session(DiagnosticSession.EXTENDED)

    # 1. Request Seed
    request = udsoncan.Request(udsoncan.services.SecurityAccess, subfunction=0x01)
    response = server._handle_security_access(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    seed = int.from_bytes(response.data[1:], "big")

    # 2. Send Correct Key
    key = seed ^ 0xDEADBEEF
    request = udsoncan.Request(
        udsoncan.services.SecurityAccess, subfunction=0x02, data=struct.pack(">I", key)
    )
    response = server._handle_security_access(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    assert not server.security_manager.locked


def test_handle_security_access_in_programming_session(server):
    """Security access must also work in Programming session (required for flashing)."""
    server.session_manager.set_session(DiagnosticSession.PROGRAMMING)

    request = udsoncan.Request(udsoncan.services.SecurityAccess, subfunction=0x01)
    response = server._handle_security_access(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse


def test_handle_security_access_blocked_in_default_session(server):
    """Security access must be rejected in Default session."""
    # Server starts in DEFAULT
    request = udsoncan.Request(udsoncan.services.SecurityAccess, subfunction=0x01)
    response = server._handle_security_access(request)
    assert response.code == udsoncan.Response.Code.ServiceNotSupportedInActiveSession


def test_handle_tester_present(server):
    request = udsoncan.Request(udsoncan.services.TesterPresent, subfunction=0x00)
    response = server._handle_tester_present(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse


def test_transfer_state_cleared_on_hard_reset(server):
    """ECU HardReset must reset flash transfer state."""
    server.session_manager.set_session(DiagnosticSession.EXTENDED)
    server.transfer_active = True
    server.flash_buffer = bytearray(b"data")

    request = udsoncan.Request(udsoncan.services.ECUReset, subfunction=0x01)
    response = server._handle_ecu_reset(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    assert server.transfer_active is False
    assert len(server.flash_buffer) == 0
