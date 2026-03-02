#!/usr/bin/env python3
"""
Integrated UDS Simulator for macOS/Windows.
Starts the Monitor and Server in separate threads.
Each uses its own 'virtual' bus instance (shared in-memory across the process).
"""

import threading
import time
import sys
import os
import can
import logging

# Add current directory to path
sys.path.append(os.getcwd())

from uds.ecu.server import ECUServer
from uds.tools.monitor import CANMonitor
from uds.tester.client import UDSClient
from uds.network.transport import CHANNEL


def run_monitor():
    # Each thread can create its own Bus(interface='virtual') and they will share messages!
    monitor = CANMonitor()
    monitor.run()


def run_server():
    # Independent ECU Server instance
    server = ECUServer()
    server.run()


def main():
    # Configure logging
    logging.basicConfig(level=logging.ERROR)  # Mute common logs to avoid noise

    print("📢 Starting CAN Monitor thread...")
    monitor_thread = threading.Thread(target=run_monitor, daemon=True)
    monitor_thread.start()
    time.sleep(1)

    print("💾 Starting ECU Server thread...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)

    print("\n🚀 UDS Simulator is running (Integrated Mode).")
    print("-" * 50)

    try:
        print("🧪 Sequence: DiagnosticSessionControl(ExtendedSession)...")
        with UDSClient() as client:
            resp = client.change_session(0x03)
            print(f"✅ Success: {resp.code_name}")

        print("🧪 Sequence: Read VIN DID (0xF190)...")
        with UDSClient() as client:
            resp = client.read_did(0xF190)
            print(f"✅ Success: {resp.code_name} | VIN: {resp.data.hex()}")

        print("\n" + "=" * 50)
        print("Simulation SUCCESSFUL! The server and client are communicating.")
        print("You can see the frames decoded by the monitor thread.")
        print("Press Ctrl+C to terminate.")
        print("=" * 50 + "\n")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down simulator...")
    except Exception as e:
        print(f"❌ Error during simulation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
