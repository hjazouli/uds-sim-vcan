"""
transport.py — OS-agnostic CAN/ISO-TP transport factory.

On Linux: uses isotp.socket (kernel SocketCAN, requires vcan0 + can-isotp module).
On macOS / Windows: uses isotp.NotifierBasedCanStack over a python-can virtual bus
                    (pure Python, no kernel modules, no hardware required).

Usage:
    from server.transport import create_connection, CHANNEL, USE_VIRTUAL

    conn, extras = create_connection(role="server", rxid=0x7E0, txid=0x7E8)
    # extras contains bus/notifier references that must be kept alive (virtual only)
"""

import sys
import logging
import threading
import platform
from typing import Any, Optional, Tuple, Dict

import can
import isotp
from udsoncan.connections import IsoTPConnection

logger = logging.getLogger("transport")

# ---------------------------------------------------------------------------
# Detect OS → choose backend
# ---------------------------------------------------------------------------
_os = platform.system()
USE_VIRTUAL: bool = _os != "Linux"   # True on macOS and Windows
CHANNEL: str = "vcan0" if not USE_VIRTUAL else "virtual_uds"

if USE_VIRTUAL:
    logger.info(f"[transport] OS={_os}  → using python-can virtual bus (channel={CHANNEL!r})")
else:
    logger.info(f"[transport] OS={_os}  → using SocketCAN / isotp kernel socket (channel={CHANNEL!r})")


# ---------------------------------------------------------------------------
# Virtual-bus custom udsoncan Connection
# ---------------------------------------------------------------------------
class VirtualIsoTPConnection:
    """
    A udsoncan-compatible connection built on top of isotp.NotifierBasedCanStack
    backed by a python-can virtual bus.

    python-can's 'virtual' bustype is an in-process loopback: every Bus instance
    bound to the same channel name sees every message sent on that channel.
    This works on macOS, Windows, and Linux — no kernel modules required.
    """

    def __init__(
        self,
        rxid: int,
        txid: int,
        channel: str = CHANNEL,
    ) -> None:
        self.rxid = rxid
        self.txid = txid
        self.channel = channel
        self._lock = threading.Lock()

        # One python-can bus per direction endpoint
        self._bus = can.interface.Bus(channel=channel, interface="virtual", receive_own_messages=False)

        addr = isotp.Address(rxid=rxid, txid=txid)
        params = isotp.params.TransportLayerParameters(
            stmin=5,        # 5 ms separation time
            blocksize=10,   # 10-block flow control
            tx_padding=0xCC,
        )
        # NotifierBasedCanStack drives the ISO-TP state machine via python-can notifier
        self._notifier = can.Notifier(self._bus, [], timeout=0)
        self._stack = isotp.NotifierBasedCanStack(
            bus=self._bus,
            notifier=self._notifier,
            address=addr,
            params=params,
        )

    # ---- udsoncan Connection interface ----

    def open(self) -> None:
        pass  # Stack is ready on construction

    def close(self) -> None:
        self._notifier.stop()
        self._bus.shutdown()

    def send(self, data: bytes, timeout: Optional[float] = 2.0) -> None:
        deadline = None
        if timeout is not None:
            import time
            deadline = time.time() + timeout
        self._stack.send(data)
        # Drive the stack until all frames are transmitted
        import time
        while self._stack.transmitting():
            self._stack.process()
            time.sleep(0.001)
            if deadline and time.time() > deadline:
                raise TimeoutError("VirtualIsoTPConnection send timed out")

    def wait_frame(self, timeout: float = 2.0) -> Optional[bytes]:
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._stack.process()
            data = self._stack.recv()
            if data is not None:
                return data
            time.sleep(0.001)
        return None

    def __enter__(self) -> "VirtualIsoTPConnection":
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------
def create_connection(
    rxid: int,
    txid: int,
    interface: str = CHANNEL,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Return (connection, extras) where connection is compatible with udsoncan.

    On Linux, returns an IsoTPConnection wrapping a kernel isotp.socket.
    On macOS/Windows, returns a VirtualIsoTPConnection.

    `extras` holds references (bus, notifier) that must be kept alive while
    the connection is open. On Linux it is empty.
    """
    if not USE_VIRTUAL:
        # --- Linux: kernel isotp socket ---
        sock = isotp.socket()
        sock.set_fc_opts(stmin=5, bs=10)
        sock.bind(interface, isotp.Address(rxid=rxid, txid=txid))
        conn = IsoTPConnection(sock)
        return conn, {"socket": sock}
    else:
        # --- macOS / Windows: python-can virtual bus ---
        conn = VirtualIsoTPConnection(rxid=rxid, txid=txid, channel=interface)
        return conn, {}
