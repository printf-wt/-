"""Windows-only loopback verification of the fixed-peer PowerShell UDP bridge."""

import json
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import threading
import time


def main():
    powershell = shutil.which("powershell.exe")
    if not powershell:
        raise RuntimeError("run this check in Windows Python")
    sockets = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(4)]
    for sock in sockets:
        sock.bind(("127.0.0.1", 0))
        sock.settimeout(2)
    local, peer, probe, unwanted = sockets
    local_port, peer_port, bridge_port = [sock.getsockname()[1] for sock in (local, peer, probe)]
    probe.close()
    script = Path(__file__).with_name("udp-bridge.ps1")
    process = subprocess.Popen([
        powershell, "-NoProfile", "-File", str(script), "-LocalUbuntuIP", "127.0.0.1",
        "-LocalPort", str(local_port), "-ListenPort", str(bridge_port), "-PeerIP", "127.0.0.1",
        "-PeerPort", str(peer_port),
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    lines = queue.Queue()
    thread = threading.Thread(target=lambda: [lines.put(line.strip()) for line in process.stdout], daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while True:
            line = lines.get(timeout=max(0.01, deadline - time.monotonic()))
            if line.startswith("READY"):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("bridge did not become ready")
        local.sendto(b"ubuntu to peer", ("127.0.0.1", bridge_port))
        assert peer.recv(1024) == b"ubuntu to peer"
        peer.sendto(b"peer to ubuntu", ("127.0.0.1", bridge_port))
        assert local.recv(1024) == b"peer to ubuntu"
        unwanted.sendto(b"unexpected source", ("127.0.0.1", bridge_port))
        for sock in (local, peer):
            sock.settimeout(0.15)
            try:
                sock.recv(1024)
            except socket.timeout:
                pass
            else:
                raise AssertionError("unconfigured sender was forwarded")
        time.sleep(1.2)
        assert process.poll() is None, "idle receive timeout should not stop the bridge"
        print(json.dumps({"status": "passed", "checks": ["local-to-peer exact bytes", "peer-to-local exact bytes",
              "unexpected sender ignored", "idle timeout continues"], "scope": "one Windows host, loopback UDP"}))
    finally:
        process.terminate()
        process.wait(timeout=5)
        for sock in sockets:
            sock.close()


if __name__ == "__main__":
    main()
