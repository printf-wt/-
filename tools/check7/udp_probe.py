"""Check the physical UDP path before starting the TCP/IP endpoints. No TCP is implemented here."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import socket
import time


MAGIC = b"CS144-POINT7-PROBE-v1 "


def listen(args):
    deadline = time.monotonic() + args.duration
    received = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        sock.settimeout(0.5)
        print(f"READY probe UDP {args.bind}:{args.port}; Ctrl+C to stop", flush=True)
        while time.monotonic() < deadline:
            try:
                payload, source = sock.recvfrom(1024)
            except (socket.timeout, ConnectionResetError):
                continue
            if len(payload) > 256 or not payload.startswith(MAGIC):
                continue
            sock.sendto(payload, source)
            received += 1
            print(json.dumps({"echo": received, "source": list(source), "bytes": len(payload)}), flush=True)
    return {"mode": "listen", "echoed": received, "status": "finished"}


def send(args):
    nonce = secrets.token_hex(16).encode("ascii")
    target = (args.peer, args.peer_port)
    results = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        for index in range(args.count):
            payload = MAGIC + nonce + b" " + str(index).encode("ascii")
            started = time.monotonic()
            deadline = started + args.timeout
            sock.sendto(payload, target)
            result = {"attempt": index + 1, "reply": False}
            while time.monotonic() < deadline:
                sock.settimeout(max(0.001, deadline - time.monotonic()))
                try:
                    received, source = sock.recvfrom(1024)
                except socket.timeout:
                    break
                except ConnectionResetError as error:
                    result["error"] = str(error)
                    break
                if received == payload:
                    result.update(reply=True, rtt_ms=(time.monotonic() - started) * 1000,
                                  source=list(source))
                    break
            results.append(result)
            print(json.dumps(result), flush=True)
    return {"mode": "send", "status": "passed" if all(item["reply"] for item in results) else "failed",
            "local_port": args.port, "target": list(target), "attempts": results,
            "scope": "UDP connectivity only; not TCP, chat or file verification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["listen", "send"])
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True, help="local UDP port of the eventual endpoint/router")
    parser.add_argument("--peer", help="physical IPv4 address of the bridge or direct peer")
    parser.add_argument("--peer-port", type=int)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=2)
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.count < 1 or args.timeout <= 0 or args.duration <= 0:
        parser.error("invalid port/count/time limit")
    if args.mode == "send":
        if args.peer is None or args.peer_port is None or not 1 <= args.peer_port <= 65535:
            parser.error("send requires --peer and --peer-port")
        try:
            socket.inet_pton(socket.AF_INET, args.peer)
        except OSError:
            parser.error("--peer must be a numeric IPv4 address")
    if args.output and args.output.exists():
        parser.error("output file already exists; use a new filename")
    result = listen(args) if args.mode == "listen" else send(args)
    result["recorded_utc"] = datetime.now(timezone.utc).isoformat()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result), flush=True)
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
