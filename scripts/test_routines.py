#!/usr/bin/env python3
"""
Test script for the new RoutineControl RIDs.
"""
import time
import sys
import os

sys.path.append(os.getcwd())

from uds.tester.client import UDSClient
from uds.tools.logging_config import setup_logging
import logging

def main():
    setup_logging()
    logger = logging.getLogger("RoutineTest")
    
    logger.info("[bold cyan]Starting RoutineControl Lifecycle Test[/]")
    
    with UDSClient() as client:
        # 1. Switch to extended session
        logger.info("Switching to Extended Session...")
        client.change_session(0x03)
        
        # 2. Test Self-Test RID (0x0203)
        logger.info("🧪 [bold]Testing RID 0x0203 (Self Test)...[/]")
        resp = client.start_routine(0x0203)
        logger.info(f"Start Response: {resp.code_name} | Data: {resp.data.hex()}")
        
        time.sleep(1)
        resp = client.request_routine_results(0x0203)
        logger.info(f"Result Response: {resp.code_name} | Data: {resp.data.hex()}")
        
        # 3. Test Programming Pre-Conditions (0x0201)
        logger.info("🧪 [bold]Testing RID 0x0201 (Programming Pre-Conditions)...[/]")
        resp = client.start_routine(0x0201)
        logger.info(f"Start Response: {resp.code_name} | Data: {resp.data.hex()}")
        
        # 4. Test Erase Memory (0xFF00) - requires programming session
        logger.info("Switching to Programming Session...")
        client.change_session(0x02)
        
        logger.info("🧪 [bold]Testing RID 0xFF00 (Erase Memory)...[/]")
        resp = client.start_routine(0xFF00)
        logger.info(f"Start Response: {resp.code_name} | Data: {resp.data.hex()}")

    logger.info("[bold green]Routine Tests COMPLETED successfully![/]")

if __name__ == "__main__":
    main()
