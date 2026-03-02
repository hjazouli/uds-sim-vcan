# UDS Simulator Project

![CI](https://github.com/hjazouli/uds-sim-vcan/actions/workflows/ci.yml/badge.svg)

A complete, robust Python project that simulates a **UDS (ISO 14229-1)** ECU server and a UDS client tester communicating over a virtual CAN bus (**vcan0**) using **ISO-TP (ISO 15765-2)**.

## Architecture & Design

```ascii
      +-----------------+           +-----------------+
      |   UDS Client    |           |    ECU Server   |
      | (Test Tester)   |           |  (The Simulator)|
      +--------+--------+           +--------+--------+
               |                             |
               |       Virtual CAN Bus        |
               | (ISO-TP over SocketCAN vcan0)|
      <--------+-----------------------------+-------->
               |
      +--------+--------+
      |  CAN Monitor    |
      | (Real-time Log) |
      +-----------------+
```

### Core Components

- **ECU Server (`server/ecu_server.py`):** Acts as the target ECU. It uses a custom dispatcher to handle UDS requests and manages internal state (sessions, security, DIDs, DTCs).
- **Session Manager (`server/session_manager.py`):** Implements the UDS session state machine. It handles transitions between `Default`, `Programming`, and `Extended` sessions and manages the **S3 timer** (5s timeout).
- **Security Manager (`server/security.py`):** Handles the challenge-response logic for `SecurityAccess (0x27)`. It generates 4-byte random seeds and validates keys using an `XOR 0xDEADBEEF` algorithm. Includes an anti-brute force lockout after 3 failed attempts.
- **Data Stores (`server/did_store.py` & `server/dtc_store.py`):** Handle persistent and volatile data. DIDs (Data Identifiers) include VIN, Serial Number, and real-time parameters like Vehicle Speed.
- **UDS Client (`client/uds_client.py`):** A simplified wrapper around `udsoncan` to facilitate writing clean, readable test sequences.
- **CAN Monitor (`monitor/can_monitor.py`):** A dedicated tool to sniff `vcan0`, decode ISO-TP frames into UDS services, and color-code results for rapid debugging.

---

## UDS Services Implemented

| Service ID | Service Name             | Subfunctions / Details                                                    |
| ---------- | ------------------------ | ------------------------------------------------------------------------- |
| **0x10**   | DiagnosticSessionControl | 0x01 (Default), 0x02 (Programming), 0x03 (Extended)                       |
| **0x11**   | ECUReset                 | 0x01 (HardReset), 0x03 (SoftReset). Only allowed in Extended session.     |
| **0x27**   | SecurityAccess           | Challenge-Response logic. Locks after 3 fails. Required for Writing DIDs. |
| **0x22**   | ReadDataByIdentifier     | Support for multiple DIDs in a single request (e.g. VIN, Speed).          |
| **0x2E**   | WriteDataByIdentifier    | Restricted by Security Access. Supports VIN and Brake Torque updates.     |
| **0x14**   | ClearDiagnosticInfo      | Wipes the current DTC database.                                           |
| **0x19**   | ReadDTCInformation       | 0x02 (ReportByStatusMask). Returns coded DTCs with status bytes.          |
| **0x3E**   | TesterPresent            | Keeps the non-default session active (Resets S3 timer).                   |
| **0x31**   | RoutineControl           | 0x01 (StartRoutine). Supports 0xFF00 (Erase) and 0xFF01 (CheckDeps).      |
| **0x34**   | RequestDownload          | Initializes firmware transfer. Informs ECU of address and size.           |
| **0x36**   | TransferData             | Streams firmware blocks with sequence counter validation.                 |
| **0x37**   | RequestTransferExit      | Finalizes the memory transfer process.                                    |

---

## Extensive Testing Suite

The project prioritizes verification with a two-tier testing approach:

### 1. Unit Testing (`server/tests/`)

Focuses on the internal logic of the ECU components without CAN overhead.

- **`test_unit.py`:** Validates State Machine transitions, Seed/Key math, DTC filtering logic, and DID read/write boundary checks.

### 2. Integration Sequences (`client/test_sequences.py`)

Run against the live server over `vcan0` to simulate real-world vehicle diagnostics.

- **Sequence 1 (Happy Path):** Full lifecycle: Session Change -> Unlock -> Read/Write -> DTC Clear -> Reset.
- **Sequence 2 (Security Lockout):** Deliberately fails security 3 times to verify NRC 0x36 (ExceededNumberOfAttempts).
- **Sequence 3 (Session Timeout):** Waits 6s without `TesterPresent` to verify automatic fallback to `DefaultSession`.
- **Sequence 4 (Service Rejection):** Tests NRC 0x7F (ServiceNotSupportedInActiveSession).
- **Sequence 5 (NRC Validation):** Deep dive into NRCs: 0x12 (SubFunctionNotSupported), 0x31 (RequestOutOfRange), 0x13 (InvalidFormat).
- **Sequence 6 (Concurrent Reads):** Verifies the server handles multiple DIDs in a single UDS frame.
- **Sequence 7 (Flashing Flow):** Complete firmware update simulation: Programming Session -> Erase -> Download -> Transfer -> Exit -> Reset.

---

## Setup & Execution

### Prerequisites

- **OS:** Linux (Ubuntu 24 recommended)
- **Tools:** `python3.11+`, `can-utils`
- **Permissions:** Root/Sudo required for `vcan` interface setup.

### 1. Installation

```bash
git clone https://github.com/hjazouli/uds-sim-vcan.git
cd uds-sim-vcan
pip install -r requirements.txt
```

### 2. Virtual CAN Setup

```bash
chmod +x setup_vcan.sh
sudo ./setup_vcan.sh
```

### 3. Running the Simulator

Open three terminal windows:

- **Window 1 (Monitor):** `python3 monitor/can_monitor.py`
- **Window 2 (ECU):** `python3 server/ecu_server.py`
- **Window 3 (Tests):** `pytest client/test_sequences.py -v`

---

## Developer Guide: How to Extend

### Adding a New DID (Data Identifier)

1. Open `server/did_store.py`.
2. Add your ID to the `_dids` dictionary in `__init__`.
3. Update `read()` and `write()` methods with the appropriate `struct.pack`/`unpack` format.

### Customizing Security

The seed/key algorithm is in `server/security.py`. You can modify `SECRET_KEY_XOR` or implement a more complex `validate_key` logic (e.g., SHA-256) for advanced simulations.

### Adding New DTCs

Update the `_initial_dtcs` list in `server/dtc_store.py`. Use the standard 2-byte or 3-byte format (the simulator uses a 3-byte representation internally for UDS compliance).

---

## CI/CD Pipeline

The included `.github/workflows/ci.yml` performs:

1. **Linting:** `flake8`, `black`, `mypy`.
2. **Virtual Environment Setup:** Initializes `vcan0` in the GitHub Runner.
3. **Automated Testing:** Starts the background ECU and runs `pytest`.
4. **Artifact Upload:** Saves the generated HTML test report.
