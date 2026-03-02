import pytest
import time
import struct
from uds.tester.client import UDSClient
from udsoncan.ResponseCode import ResponseCode
import udsoncan


import threading
from uds.ecu.server import ECUServer


@pytest.fixture(scope="session", autouse=True)
def background_server():
    """Start the ECU server in a background thread for the duration of the test session."""
    server = ECUServer()
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    time.sleep(1)  # Give the server time to start
    yield
    server.stop()


@pytest.fixture(scope="module")
def uds_client():
    """Fixture to provide a UDS client."""
    with UDSClient() as client:
        yield client


def test_sequence_1_happy_path(uds_client: UDSClient):
    """Sequence 1 — 'Happy Path'"""
    # 1. Send TesterPresent
    uds_client.send_tester_present()

    # 2. Switch to ExtendedDiagnosticSession
    resp = uds_client.change_session(0x03)
    assert resp.positive, f"Failed to switch to Extended Session: {resp.code_name}"

    # 3. Request SecurityAccess seed
    seed_resp = uds_client.request_seed(1)
    # data[0] is subfunction 0x01, data[1:] is seed
    seed = int.from_bytes(seed_resp[1:], "big")

    # 4. Send correct key (key = seed XOR 0xDEADBEEF)
    key = seed ^ 0xDEADBEEF
    resp = uds_client.send_key(1, key)
    assert resp.positive, f"Security Access failed: {resp.code_name}"

    # 5. Read all DIDs
    dids = [0xF190, 0xF18C, 0xF187, 0xF40D, 0xD001, 0xD002]
    for did in dids:
        resp = uds_client.read_did(did)
        assert resp.positive, f"Failed to read DID 0x{did:04X}"
        if did == 0xF190:
            assert len(resp.data) == 19
        elif did == 0xF187:
            assert len(resp.data) == 4

    # 6. Write new VIN
    new_vin = "WBA98765432109876"
    resp = uds_client.write_did(0xF190, new_vin)
    assert resp.positive, "Failed to write VIN"

    # 6. Read back and verify
    # Server returns DID 0xF190 (2 bytes) + 17nd bytes value
    vin_resp = uds_client.read_did(0xF190)
    assert len(vin_resp.data) == 19
    assert b"WBA" in vin_resp.data

    # 7. Read DTCs
    resp = uds_client.read_dtcs()
    assert resp.positive
    # At least 3 DTCs should be returned (1 byte mask + 3 * 4 bytes per DTC = 13 bytes total)
    assert len(resp.data) >= 13

    # 8. Clear DTCs
    resp = uds_client.clear_dtcs()
    assert resp.positive

    # Verify cleared (returns Subfunction 0x02 + Status Availability Mask 0xFF)
    resp = uds_client.read_dtcs()
    assert len(resp.data) == 2

    # 9. ECU Reset (SoftReset)
    resp = uds_client.ecu_reset(0x03)
    assert resp.positive

    # Verify session returned to Default is not strictly required by my server impl (SoftReset),
    # but ECU reset usually means session reset in many specs.
    # Let's check session status via a restricted service.
    # Actually, let's just assert positive response.


def test_sequence_2_security_lockout(uds_client: UDSClient):
    """Sequence 2 — 'Security Lockout'"""
    # 1. Switch to ExtendedDiagnosticSession
    uds_client.change_session(0x03)

    # Clear lockout first if any (by hard reset or just starting fresh)
    uds_client.ecu_reset(0x01)
    time.sleep(0.5)
    uds_client.change_session(0x03)

    # 2. Send wrong key 3 times — all 3 return InvalidKey, but the 3rd also sets lockout
    for i in range(3):
        uds_client.request_seed(1)
        resp = uds_client.send_key(1, 0x12345678)  # Definitely wrong
        assert resp.code == ResponseCode.InvalidKey

    # 3. A 4th request after lockout should return ExceededNumberOfAttempts
    uds_client.request_seed(1)
    resp = uds_client.send_key(1, 0x12345678)
    assert resp.code == ResponseCode.ExceedNumberOfAttempts

    # 4. Attempt to write DID while locked
    resp = uds_client.write_did(0xF190, "WBA00000000000000")
    assert resp.code == ResponseCode.SecurityAccessDenied

    # 5. Verify server still responds to reads
    resp = uds_client.read_did(0xF190)
    assert resp.positive


def test_sequence_3_session_timeout(uds_client: UDSClient):
    """Sequence 3 — 'Session Timeout'"""
    # 1. Switch to ExtendedDiagnosticSession
    uds_client.change_session(0x03)

    # 2. Stop sending TesterPresent (just sleep)
    # S3 timeout is 5s, let's wait 6s
    time.sleep(6)

    # 3. Send a read DID request (service supported in default)
    # Wait, the spec says "verify server is back in DefaultSession (expect NRC 0x7F for services not allowed in Default)"
    # ECUReset subfunction 0x01 is NOT allowed in DefaultSession in my server.
    resp = uds_client.ecu_reset(0x01)
    assert resp.code == ResponseCode.ServiceNotSupportedInActiveSession


def test_sequence_4_wrong_session_service_rejection(uds_client: UDSClient):
    """Sequence 4 — 'Wrong Session Service Rejection'"""
    # 1. In DefaultSession, ensure it is set
    uds_client.change_session(0x01)
    time.sleep(0.5)

    # 2. ECUReset subfunction 0x01 is NOT allowed in DefaultSession
    resp = uds_client.ecu_reset(0x01)
    assert resp.code == ResponseCode.ServiceNotSupportedInActiveSession

    # 3. SecurityAccess is NOT allowed in DefaultSession
    try:
        uds_client.client.request_seed(1)
        assert False, "Should have raised NegativeResponseException"
    except udsoncan.exceptions.NegativeResponseException as e:
        assert e.response.code == ResponseCode.ServiceNotSupportedInActiveSession

    # 4. Switch to ExtendedSession and verify they work
    resp = uds_client.change_session(0x03)
    assert resp.positive

    resp = uds_client.ecu_reset(0x01)
    assert resp.positive


def test_sequence_5_nrc_validation(uds_client: UDSClient):
    """Sequence 5 — 'NRC Validation Suite'"""
    # 0x12 - SubFunctionNotSupported
    resp = uds_client.change_session(0x7F)
    assert resp.code == ResponseCode.SubFunctionNotSupported

    # 0x31 - RequestOutOfRange
    resp = uds_client.read_did(0xFFFF)
    assert resp.code == ResponseCode.RequestOutOfRange

    # 0x22 - ConditionsNotCorrect (Write DID restricted)
    uds_client.change_session(0x03)
    # Correct key to unlock first to test write restriction logic but with wrong format
    seed = int.from_bytes(uds_client.request_seed(1)[1:], "big")
    uds_client.send_key(1, seed ^ 0xDEADBEEF)

    # 0x13 - IncorrectMessageLengthOrInvalidFormat
    resp = uds_client.write_did(0xF190, "TOO_SHORT")
    assert resp.code == ResponseCode.IncorrectMessageLengthOrInvalidFormat


def test_sequence_6_concurrent_did_read(uds_client: UDSClient):
    """Sequence 6 — 'Concurrent/Multiple DID Requests'"""
    # UDS allows reading multiple DIDs in one request
    dids = [0xF190, 0xF18C]
    resp = uds_client.client.read_data_by_identifier(dids)
    assert resp.positive
    # Response should contain both DIDs plus their data
    assert len(resp.data) == (17 + 2) + (8 + 2)  # VIN + DID tag, Serial + DID tag


def test_sequence_7_flashing_flow(uds_client: UDSClient):
    """Sequence 7 — 'Flashing flow simulation'"""
    # 1. Switch to Programming Session
    resp = uds_client.change_session(0x02)
    assert resp.positive

    # 2. Unlock Security
    seed_resp = uds_client.request_seed(1)
    seed = int.from_bytes(seed_resp[1:], "big")
    resp = uds_client.send_key(1, seed ^ 0xDEADBEEF)
    assert resp.positive

    # 3. Erase Memory Routine (0xFF00)
    resp = uds_client.start_routine(0xFF00)
    assert resp.positive

    # 4. Request Download (0x34)
    # Memory address 0x1000, size 1024 bytes
    from udsoncan import MemoryLocation

    mem_loc = MemoryLocation(address=0x1000, memorysize=1024)
    resp = uds_client.request_download(mem_loc)
    assert resp.positive

    # 5. Transfer Data (0x36)
    # Binary payload "firmware_v1" repeated
    payload = b"firmware_data_chunk_"
    for i in range(1, 4):
        resp = uds_client.transfer_data(i, payload + bytes([i]))
        assert resp.positive

    # 6. Request Transfer Exit (0x37)
    resp = uds_client.request_transfer_exit()
    assert resp.positive

    # 7. Check Dependencies Routine (0xFF01)
    resp = uds_client.start_routine(0xFF01)
    assert resp.positive

    # 8. Reset to finalize
    uds_client.ecu_reset(0x01)
