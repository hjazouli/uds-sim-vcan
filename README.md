# UDS Simulator Project

![CI](https://github.com/hjazouli/uds-sim-vcan/actions/workflows/ci.yml/badge.svg)

A complete, robust Python project that simulates a **UDS (ISO 14229-1)** ECU server and a UDS client tester communicating over a virtual CAN bus using **ISO-TP (ISO 15765-2)**.

## Architecture & Design

```ascii
      +-----------------+           +-----------------+
      |   UDS Client    |           |    ECU Server   |
      | (Tester Unit)   |           |  (The Simulator)|
      +--------+--------+           +--------+--------+
               |                             |
               |       Virtual CAN Bus        |
               | (Cross-Platform Transport)   |
      <--------+-----------------------------+-------->
               |
      +--------+--------+
      |  CAN Monitor    |
      | (Real-time Log) |
      +-----------------+
```

## Project Structure (Logical Units)

The project is organized into self-contained logical units, bundling core logic with relevant tests.

- **`uds/ecu/`**: **ECU Server Unit.** Manages sessions, security challenge-response, and data stores (DIDs/DTCs). Includes internal unit tests.
- **`uds/tester/`**: **Tester Unit.** A high-level wrapper around `udsoncan` designed for writing clean diagnostic sequences.
- **`uds/network/`**: **Transport Unit.** Provides the OS-agnostic factory that enables this project to run on macOS/Windows via a virtual bus and the TCP bridge.
- **`uds/tools/`**: **Utility Unit.** Contains the real-time UDS protocol decoder and monitor.
- **`scripts/`**: Convenience entry points for integrated simulation.

---

## UDS Services Implemented

| Service ID | Service Name             | Subfunctions / Details                                       |
| ---------- | ------------------------ | ------------------------------------------------------------ |
| **0x10**   | DiagnosticSessionControl | 0x01 (Default), 0x02 (Programming), 0x03 (Extended)          |
| **0x11**   | ECUReset                 | 0x01 (HardReset), 0x03 (SoftReset)                           |
| **0x14**   | ClearDiagnosticInfo      | Wipes the current DTC database                               |
| **0x19**   | ReadDTCInformation       | 0x02 (ReportByStatusMask)                                    |
| **0x22**   | ReadDataByIdentifier     | Support for multiple DIDs (VIN, Serial, Speed)               |
| **0x23**   | ReadMemoryByAddress      | Dynamic memory access (FLASH/RAM regions)                    |
| **0x27**   | SecurityAccess           | Challenge-Response logic. Locks after 3 fails                |
| **0x28**   | CommunicationControl     | 0x00 (Enable), 0x03 (Disable) Rx/Tx                          |
| **0x2E**   | WriteDataByIdentifier    | Restricted by Security Access. Supports VIN and Brake Torque |
| **0x2F**   | IOCBI                    | Input Output Control (Fan, Fuel Pump, Lights)                |
| **0x31**   | RoutineControl           | Multiple RIDs (Erase Memory, Self Test, Dependencies)        |
| **0x34**   | RequestDownload          | Initializes firmware transfer                                |
| **0x35**   | RequestUpload            | Prepares data retrieval from ECU                             |
| **0x36**   | TransferData             | Streams firmware blocks with sequence counter validation     |
| **0x37**   | RequestTransferExit      | Finalizes the memory transfer process                        |
| **0x38**   | RequestFileTransfer      | 0x01 (Add File) simulation                                   |
| **0x3E**   | TesterPresent            | Keeps the non-default session active (Resets S3 timer)       |

---

## Setup & Execution

### 1. Installation

```bash
git clone https://github.com/hjazouli/uds-sim-vcan.git
cd uds-sim-vcan
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Quick Start: Integrated Simulation

Run everything (Monitor + Server + Basic Client) in a single terminal:

```bash
python3 scripts/simulate.py
```

### 3. Professional Setup: Multi-Terminal

To develop or debug across separate terminal windows on macOS:

1.  **Terminal 1 (Bridge):** `python3 uds/network/bridge.py`
2.  **Terminal 2 (Monitor):** `python3 uds/tools/monitor.py`
3.  **Terminal 3 (ECU):** `python3 uds/ecu/server.py`
4.  **Terminal 4 (Tester):** `pytest uds/tester/tests/test_sequences.py`

---

## Testing

The project uses `pytest` for all testing levels. Reports are saved in the `logs/` directory.

### Logic-Units (Unit Tests)

Validates internal ECU math and state transitions without networking overhead.

```bash
pytest uds/ecu/tests/
```

### Integrated Sequences (Functional Tests)

Run against a live ECU server to verify protocol compliance.

```bash
# In a separate terminal, start the ECU: python3 uds/ecu/server.py
pytest uds/tester/tests/test_sequences.py
```

---

## CI/CD Pipeline

The project is CI-ready with a multi-stage validation approach:

1.  **Static Analysis:** Linting and type checking.
2.  **Logic Guard:** Fast execution of ECU unit tests.
3.  **System Guard:** Full diagnostic sequence verification over a virtual network.
