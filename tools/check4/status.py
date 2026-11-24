"""Show the state of collected paths without stopping or altering any measurement."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from metrics import parse_ping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("writeups/check4-data/network2"))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    paths = sorted(args.root.glob("*/metadata.json"))
    if not paths:
        parser.error("No metadata.json found beneath the data root")
    for path in paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        age = (now - datetime.fromisoformat(metadata["started_utc"])).total_seconds()
        elapsed = metadata.get("elapsed_s", age)
        remaining = max(0, metadata["duration_requested_s"] - elapsed)
        raw = (path.parent / "ping.txt").read_text(encoding="utf-8")
        try:
            measurement = parse_ping(raw, allow_partial=True)
            latest = max((r.timestamp for r in measurement.replies.values()), default=None)
            reply_age = (f"{max(0, datetime.now(timezone.utc).timestamp() - latest):.1f}s ago"
                         if latest else "none observed")
            print(f"{metadata['host']}: {metadata['state']}, "
                  f"elapsed {elapsed / 60:.1f}min, remaining {remaining / 60:.1f}min, "
                  f"{len(measurement.replies)}/{measurement.sent} replies/sequences, latest reply {reply_age}")
        except ValueError as error:
            print(f"{metadata['host']}: {metadata['state']}, data not ready: {error}")


if __name__ == "__main__":
    main()
