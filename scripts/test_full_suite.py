#!/usr/bin/env python3
"""
Test script for the new UDS services (0x23, 0x28, 0x2F, 0x35).
"""

import sys
import os
import udsoncan

sys.path.append(os.getcwd())

from uds.tester.client import UDSClient
from uds.tools.logging_config import setup_logging
import logging


def main():
    setup_logging()
    logger = logging.getLogger("FullSuiteTest")

    logger.info("[bold cyan]Starting Full UDS Suite Service Test[/]")

    with UDSClient() as client:
        # Unlock ECU first
        logger.info("Unlocking ECU for restricted services...")
        client.change_session(0x03)
        seed = client.request_seed(1)
        # key = seed ^ 0xDEADBEEF
        seed_int = int.from_bytes(seed, "big")
        key_int = seed_int ^ 0xDEADBEEF
        client.send_key(1, key_int)

        # 1. Test 0x23 - Read Memory By Address
        logger.info("🧪 [bold]Testing Service 0x23 (Read Memory By Address)...[/]")
        loc = udsoncan.MemoryLocation(
            address=0x08000000, memorysize=8, address_format=32, memorysize_format=8
        )
        resp = client.read_memory(loc)
        logger.info(f"Read Response: {resp.code_name} | Data: {resp.data.hex()}")

        # 2. Test 0x2F - IOCBI
        logger.info("🧪 [bold]Testing Service 0x2F (IO Control: Fan @ 0x0101)...[/]")
        # 0x03 = Short term adjustment, 0x01 = On
        resp = client.io_control(0x0101, 0x03, values=b"\x01")
        logger.info(f"IO Start Response: {resp.code_name} | Data: {resp.data.hex()}")

        # 3. Test 0x28 - Communication Control
        logger.info("🧪 [bold]Testing Service 0x28 (Disable RX/TX)...[/]")
        resp = client.communication_control(0x03, 0x01)  # 0x03 = DisableRxAndTx
        logger.info(f"Comm Disable Response: {resp.code_name}")

        # 4. Test 0x35 - Request Upload
        logger.info("🧪 [bold]Testing Service 0x35 (Request Upload)...[/]")
        loc = udsoncan.MemoryLocation(
            address=0x08000000, memorysize=256, address_format=32, memorysize_format=16
        )
        resp = client.request_upload(loc)
        logger.info(f"Upload Request Response: {resp.code_name} | MaxBlock: {resp.data.hex()}")

    logger.info("[bold green]Full Suite Tests COMPLETED![/]")


if __name__ == "__main__":
    main()
