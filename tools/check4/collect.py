"""Collect timestamped Linux ping output without changing network configuration."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=3602)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--size", type=int, default=56)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Run this collector inside Ubuntu/WSL (Linux iputils ping required).")
    if args.duration < 1 or args.interval < 0.2 or not 0 <= args.size <= 1400:
        parser.error("Use duration >= 1, interval >= 0.2 seconds, and size in [0, 1400].")
    if args.duration / args.interval >= 65535:
        parser.error("Split the measurement into sessions shorter than the 16-bit ICMP sequence cycle.")
    args.output.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output / "metadata.json"
    raw_path = args.output / "ping.txt"
    if metadata_path.exists() or raw_path.exists():
        parser.error("Output already contains a measurement; choose a new directory.")
    address = socket.gethostbyname(args.host)
    command = ["ping", "-4", "-D", "-n", "-O", "-i", str(args.interval),
               "-w", str(args.duration), "-W", "2", "-s", str(args.size), address]
    metadata = {
        "host": args.host, "ipv4": address, "command": command,
        "started_utc": utc_now(), "duration_requested_s": args.duration,
        "interval_s": args.interval, "payload_bytes": args.size,
        "platform": "Linux/WSL", "state": "running",
        "note": "Raw ping timestamps are reply times; missing replies are resolved from final statistics.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    environment = dict(os.environ, LC_ALL="C", TZ="UTC")
    started = time.monotonic()
    interrupted = False
    with raw_path.open("x", encoding="utf-8") as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, env=environment)
        print(f"Started {args.host} ({address}), PID {process.pid}, {args.duration}s", flush=True)
        try:
            returncode = process.wait()
        except KeyboardInterrupt:
            interrupted = True
            process.send_signal(signal.SIGINT)
            try:
                returncode = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                returncode = process.wait()
    elapsed = time.monotonic() - started
    state = "finished"
    if interrupted:
        state = "interrupted"
    elif returncode not in (0, 1):
        state = "failed"
    elif elapsed < args.duration - 0.5:
        state = "ended_early"
    metadata.update(ended_utc=utc_now(), elapsed_s=elapsed,
                    returncode=returncode, state=state)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Finished: {metadata_path}; ping exit {returncode}", flush=True)
    if state != "finished":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
