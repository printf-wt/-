"""Run three bounded ICMP rate trials (each <=8 seconds, payload <=1200 bytes)."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from metrics import parse_ping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Run inside Ubuntu/WSL.")
    args.output.mkdir(parents=True, exist_ok=False)
    address = socket.gethostbyname(args.host)
    trials = []
    for size, interval, count in [(56, 0.2, 25), (256, 0.1, 50), (1200, 0.05, 100)]:
        command = ["ping", "-4", "-D", "-n", "-i", str(interval), "-s", str(size),
                   "-c", str(count), "-w", "8", "-W", "1", address]
        start_utc = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True,
                                env=dict(os.environ, LC_ALL="C", TZ="UTC"), timeout=10)
        elapsed = time.monotonic() - start
        name = f"ping-{size}bytes-{interval}s.txt"
        (args.output / name).write_text(result.stdout + result.stderr, encoding="utf-8")
        measurement = parse_ping(result.stdout)
        trial = {
            "host": args.host, "ipv4": address, "started_utc": start_utc,
            "payload_bytes": size, "interval_s": interval, "count_requested": count,
            "sent": measurement.sent, "received": len(measurement.replies),
            "elapsed_s": elapsed, "returncode": result.returncode, "command": command,
            "nominal_request_payload_bps": size * 8 / interval,
            "observed_request_payload_bps": size * 8 * measurement.sent / elapsed,
            "observed_reply_payload_bps": size * 8 * len(measurement.replies) / elapsed,
            "raw_log": name,
        }
        trials.append(trial)
        (args.output / "trials.json").write_text(json.dumps(trials, indent=2) + "\n", encoding="utf-8")
        print(f"{args.host}: {size} bytes/{interval}s, "
              f"{len(measurement.replies)}/{measurement.sent} replies, {elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    main()
