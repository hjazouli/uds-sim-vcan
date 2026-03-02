import pytest
import udsoncan
from server.ecu_server import ECUServer
from server.session_manager import DiagnosticSession
import struct

@pytest.fixture
def server():
    """Fixture to provide an ECUServer instance for testing logic."""
    # We don't start the actual network loop for unit tests of the logic
    return ECUServer(interface="vcan0")

def test_ecu_server_initialization(server):
    assert server.interface == "vcan0"
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
    request = udsoncan.Request(udsoncan.services.ReadDataByIdentifier, data=struct.pack(">H", 0xF190))
    response = server._handle_read_did(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    assert b"WBA12345678901234" in response.data

    # Test reading non-existent DID
    request = udsoncan.Request(udsoncan.services.ReadDataByIdentifier, data=struct.pack(">H", 0xFFFF))
    response = server._handle_read_did(request)
    assert response.code == udsoncan.Response.Code.RequestOutOfRange

def test_handle_security_access_flow(server):
    # 1. Request Seed
    request = udsoncan.Request(udsoncan.services.SecurityAccess, subfunction=0x01)
    # SecurityAccess requires being in Extended or Programming session in most impls, 
    # but let's see what our server does.
    server.session_manager.set_session(DiagnosticSession.EXTENDED)
    
    response = server._handle_security_access(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    seed = int.from_bytes(response.data[1:], "big")

    # 2. Send Correct Key
    key = seed ^ 0xDEADBEEF
    request = udsoncan.Request(udsoncan.services.SecurityAccess, subfunction=0x02, data=struct.pack(">I", key))
    response = server._handle_security_access(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
    assert not server.security_manager.locked

def test_handle_tester_present(server):
    request = udsoncan.Request(udsoncan.services.TesterPresent, subfunction=0x00)
    response = server._handle_tester_present(request)
    assert response.code == udsoncan.Response.Code.PositiveResponse
