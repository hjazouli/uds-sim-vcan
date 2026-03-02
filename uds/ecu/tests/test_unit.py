import pytest
import struct
from uds.ecu.did_store import DIDStore
from uds.ecu.dtc_store import DTCStore
from uds.ecu.security import SecurityManager
from uds.ecu.session_manager import SessionManager, DiagnosticSession

# --- DIDStore Tests ---


def test_did_store_read_write():
    store = DIDStore()

    # Test read VIN
    vin = store.read(0xF190)
    assert vin == b"INV4567890ABCDEFG"

    # Test write VIN
    new_vin = b"INV00000000000000"
    store.write(0xF190, new_vin)
    assert store.read(0xF190) == new_vin

    # Test read Speed
    speed_bytes = store.read(0x4004)
    speed = struct.unpack(">H", speed_bytes)[0]
    assert speed == 3500


def test_did_store_reset():
    store = DIDStore()
    store.write(0x4002, struct.pack(">H", 1000))
    store.reset_to_defaults()
    assert struct.unpack(">H", store.read(0x4002))[0] == 150


# --- DTCStore Tests ---


def test_dtc_store_filtering():
    store = DTCStore()

    # Mask 0x01 (Active) should return P0A78
    active_dtcs = store.get_dtcs_by_status_mask(0x01)
    assert any(dtc["name"] == "P0A78" for dtc in active_dtcs)

    # Mask 0x04 (Pending) should return P0C05
    pending_dtcs = store.get_dtcs_by_status_mask(0x04)
    assert any(dtc["name"] == "P0C05" for dtc in pending_dtcs)


def test_dtc_store_clear():
    store = DTCStore()
    store.clear_dtcs()
    assert len(store.get_dtcs_by_status_mask(0xFF)) == 0

    store.reset()
    assert len(store.get_dtcs_by_status_mask(0xFF)) == 6


# --- SecurityManager Tests ---


def test_security_manager_validation():
    sm = SecurityManager()
    assert sm.locked == True

    seed_bytes = sm.generate_seed()
    seed = int.from_bytes(seed_bytes, "big")

    # Wrong key
    assert sm.validate_key(struct.pack(">I", 0x12345678)) == False
    assert sm.locked == True

    # Correct key
    key = seed ^ 0xDEADBEEF
    assert sm.validate_key(struct.pack(">I", key)) == True
    assert sm.locked == False


def test_security_manager_lockout():
    sm = SecurityManager()
    sm.generate_seed()

    for _ in range(3):
        sm.validate_key(b"\x00\x00\x00\x00")

    assert sm.lockout_active == True
    assert sm.validate_key(b"\x00\x00\x00\x00") == False


# --- SessionManager Tests ---


def test_session_manager_transitions():
    timeout_called = False

    def on_timeout():
        nonlocal timeout_called
        timeout_called = True

    sm = SessionManager(on_timeout=on_timeout)
    assert sm.current_session == DiagnosticSession.DEFAULT

    sm.set_session(DiagnosticSession.EXTENDED)
    assert sm.current_session == DiagnosticSession.EXTENDED
    assert sm.is_extended == True


def test_session_manager_timeout(monkeypatch):
    timeout_called = False

    def on_timeout():
        nonlocal timeout_called
        timeout_called = True

    sm = SessionManager(on_timeout=on_timeout)
    sm.set_session(DiagnosticSession.EXTENDED)

    # Fast-forward time
    import time

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 6.0)

    sm.check_timeout()
    assert sm.current_session == DiagnosticSession.DEFAULT
    assert timeout_called == True
