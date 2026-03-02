#!/usr/bin/env python3
import threading
import time
import sys
import os
import logging
import subprocess
import signal

# Add current directory to path
sys.path.append(os.getcwd())

from uds.ecu.server import ECUServer
from uds.web import api

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DashboardLauncher")

def run_ecu():
    logger.info("Starting ECU Simulation Thread...")
    server = ECUServer()
    # Inject server into api for status reporting
    api.ecu_server = server
    server.run()

def run_backend():
    logger.info("Starting FastAPI Backend (Port 8000)...")
    import uvicorn
    uvicorn.run(api.app, host="0.0.0.0", port=8000, log_level="error")

def run_frontend():
    logger.info("Starting Vite Frontend (Port 5173)...")
    frontend_path = os.path.join(os.getcwd(), "uds", "web", "dashboard")
    subprocess.run(["npm", "run", "dev"], cwd=frontend_path)

def main():
    print("\n" + "="*60)
    print(" 🏎️  UDS-SIMULATOR PREMIUM DASHBOARD LAUNCHER")
    print("="*60 + "\n")
    
    # ECU Thread
    ecu_thread = threading.Thread(target=run_ecu, daemon=True)
    ecu_thread.start()
    time.sleep(1)
    
    # Backend Thread
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    time.sleep(1)
    
    print("\n✅ Dashboard Ready!")
    print("🔗 API: http://localhost:8000")
    print("🎨 Interface: http://localhost:5173")
    print("\n" + "-"*60)
    print("Press Ctrl+C to terminate the simulation.")
    print("-"*60 + "\n")
    
    try:
        # Start the frontend in the main thread (or keep it alive)
        run_frontend()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down UDS ecosystem...")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
