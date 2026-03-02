#!/usr/bin/env python3
"""
Diagnostic File Viewer (ECU Explorer).
Reads the central diagnostic configuration and displays the ECU capabilities.
"""

import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from uds.tools.logging_config import setup_logging
import logging


def main():
    setup_logging()
    logger = logging.getLogger("ECUExplorer")

    config_path = "uds/config/ecu_diag.json"

    if not os.path.exists(config_path):
        logger.error(f"Diagnostic file not found at {config_path}")
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    # Header
    ecu = config.get("ecu", {})
    logger.info(f" ECU: [bold cyan]{ecu.get('name')}[/]")
    logger.info(
        f" HW: [bold]{ecu.get('hardware_version')}[/] | SW: [bold]{ecu.get('software_version')}[/]"
    )
    logger.info("-" * 40)

    # Sessions
    logger.info("[bold yellow]Available Sessions:[/]")
    for sid, info in config.get("sessions", {}).items():
        logger.info(f" {sid}: {info['name']} (P2: {info['p2']}ms, P2*: {info['p2_star']}ms)")

    # DIDs
    logger.info("\n[bold yellow]Data Identifiers (DIDs):[/]")
    for did in config.get("dids", []):
        logger.info(f" {did['id']}: {did['name']} ({did['size']} bytes, Type: {did['type']})")

    # DTCs
    logger.info("\n[bold yellow]DTC Database:[/]")
    for dtc in config.get("dtcs", []):
        logger.info(f" {dtc['code']}: {dtc['name']} - {dtc['description']}")

    # Routines
    logger.info("\n[bold yellow]Diagnostic Routines (RIDs):[/]")
    for rid in config.get("routines", []):
        logger.info(f" {rid['id']}: {rid['name']}")

    # Memory map
    logger.info("\n[bold yellow]Virtual Memory Map:[/]")
    for name, mem in config.get("memory", {}).items():
        logger.info(f" {name.upper():<10} @ 0x{mem['start']:08X} ({mem['size']} bytes)")

    logger.info("-" * 40)
    logger.info("[bold green]Diagnostic discovery complete.[/]")


if __name__ == "__main__":
    main()
