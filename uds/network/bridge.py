#!/usr/bin/env python3
"""
Minimal socketcand-like server for macOS / Windows.
Allows cross-process communication for python-can using the 'socketcand' interface.
"""
import socket
import select
import threading

def handle_client(conn, addr, clients, lock):
    print(f"📡 Connection from {addr}")
    try:
        # Minimal socketcand handshake: server must send < hi >
        conn.sendall(b"< hi >")
        
        while True:
            data = conn.recv(4096)
            if not data: break
            
            # Simple line-based protocol parsing
            for line in data.split(b">"):
                if not line.strip(): continue
                msg = line.strip() + b">"
                
                # Handle commands like < open ... >
                if b"< open" in msg:
                    conn.sendall(b"< ok >")
                    continue
                
                # Rebroadcast < send ... > messages to all other clients
                if b"< send" in msg:
                    with lock:
                        for c in clients:
                            if c != conn:
                                try: c.sendall(msg)
                                except: pass
    except Exception as e:
        print(f"⚠️ Error with {addr}: {e}")
    finally:
        with lock: 
            if conn in clients: clients.remove(conn)
        conn.close()
        print(f"👋 Disconnected {addr}")

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 29536)) # Default socketcand port
    server.listen(5)
    
    clients = []
    lock = threading.Lock()
    
    print("🚌 TCP CAN Bridge (socketcand-lite) started on 127.0.0.1:29536")
    print("All simulator components will now see each other across terminals.")
    
    try:
        while True:
            conn, addr = server.accept()
            with lock: clients.append(conn)
            threading.Thread(target=handle_client, args=(conn, addr, clients, lock), daemon=True).start()
    except KeyboardInterrupt:
        print("\n🛑 Bridge stopping.")
    finally:
        server.close()

if __name__ == "__main__":
    main()
