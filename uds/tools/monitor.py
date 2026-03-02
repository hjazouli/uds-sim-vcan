import os
import time
import csv
import logging
import datetime
from typing import Optional

import can
import sys
from udsoncan import services

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class CANMonitor:
    """
    Real-time CAN frame logger and UDS decoder.
    """

    def __init__(self, interface: str = "vcan0", bus: Optional[can.BusABC] = None) -> None:
        self.interface = interface
        self.log_file = f"logs/can_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

        self.csv_file = open(self.log_file, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(
            ["Timestamp", "ID", "Direction", "Type", "Service", "Details", "Data"]
        )

        # Use the appropriate CAN interface based on OS
        if bus:
            self.bus = bus
        elif os.name == "posix" and sys.platform == "darwin":
            # macOS – use the virtual backend
            self.bus = can.interface.Bus(channel=self.interface, interface="virtual")
        else:
            # Linux or other platforms – default to socketcan
            self.bus = can.interface.Bus(channel=self.interface, bustype="socketcan")

    def decode_uds(self, msg: can.Message) -> str:
        """Simple UDS decoding logic."""
        data = msg.data
        if not data:
            return "Empty"

        # Multi-frame logic not fully implemented here for simplicity,
        # but we can decode single frames (SF) or First Frames (FF).
        pci = data[0]
        frame_type = (pci & 0xF0) >> 4

        if frame_type == 0:  # Single Frame
            sid = data[1]
            length = pci & 0x0F
        elif frame_type == 1:  # First Frame
            sid = data[2]
            length = ((pci & 0x0F) << 8) | data[1]
        else:
            return f"Type {frame_type}"

        # Check if response or request
        is_response = (sid & 0x40) != 0
        actual_sid = sid & ~0x40 if is_response else sid

        service_name = "Unknown"
        for name, entry in services.__dict__.items():
            if hasattr(entry, "request_id") and entry.request_id == actual_sid:
                service_name = name
                break

        if is_response:
            if data[1] == 0x7F:  # Negative Response
                nrc = data[3] if frame_type == 0 else data[4]
                return f"Response: NEGATIVE (NRC: 0x{nrc:02X})"
            return f"Response: POSITIVE"
        else:
            return f"ServiceID: 0x{actual_sid:02X} ({service_name})"

    def run(self) -> None:
        """Start monitoring."""
        print(f"Monitoring {self.interface}... Logging to {self.log_file}")
        print("Press Ctrl+C to stop.\n")

        try:
            while True:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    ts = datetime.datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S.%f")[:-3]
                    direction = "RX" if msg.arbitration_id == 0x7E8 else "TX"
                    decoded = self.decode_uds(msg)

                    # Formatting for console
                    color = RESET
                    if "POSITIVE" in decoded:
                        color = GREEN
                    elif "NEGATIVE" in decoded:
                        color = RED
                    elif "ServiceID" in decoded:
                        color = YELLOW

                    data_hex = " ".join([f"{b:02X}" for b in msg.data])
                    print(
                        f"[{ts}] ID:0x{msg.arbitration_id:03X} → {direction} | {color}{decoded}{RESET} | Data: {data_hex}"
                    )

                    # Log to CSV
                    self.csv_writer.writerow(
                        [
                            ts,
                            hex(msg.arbitration_id),
                            direction,
                            "UDS",
                            decoded.split(" (")[0],
                            decoded,
                            data_hex,
                        ]
                    )
                    self.csv_file.flush()

        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
        finally:
            self.csv_file.close()
            self.bus.shutdown()


if __name__ == "__main__":
    monitor = CANMonitor()
    monitor.run()
