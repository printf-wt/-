"""Export sequence-aware metrics, CSV and figures from one collected ping path."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from metrics import adjacent_pairs, parse_ping, summarize


LOCAL_TIME = timezone(timedelta(hours=8))
BLUE, ORANGE = "#2463a6", "#be592b"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "savefig.dpi": 160})


def save_figure(fig, output, name):
    fig.savefig(output / f"{name}.png", dpi=160)
    fig.savefig(output / f"{name}.pdf")
    plt.close(fig)


def plot_path(measurement, stats, metadata, output):
    title = metadata["host"] + (" - PREVIEW (collection running)" if not stats["finalized"] else "")
    replies = sorted(measurement.replies.values(), key=lambda reply: reply.sequence)
    rtts = sorted(reply.rtt_ms for reply in replies)

    fig, ax = plt.subplots(figsize=(7.4, 2.9), layout="constrained")
    times = [datetime.fromtimestamp(reply.timestamp, LOCAL_TIME) for reply in replies]
    ax.scatter(times, [r.rtt_ms for r in replies], s=3, alpha=0.5, color=BLUE, rasterized=True)
    ax.set(title=f"{title}: RTT over time", xlabel="Reply time (UTC+08:00)", ylabel="RTT (ms)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=LOCAL_TIME))
    ax.grid(alpha=0.2)
    if not replies:
        ax.text(0.5, 0.5, "No replies: RTT is unavailable", ha="center", transform=ax.transAxes)
    save_figure(fig, output, "rtt-time")

    fig, ax = plt.subplots(figsize=(7.4, 2.9), layout="constrained")
    if rtts:
        # Include the zero-height left edge, so the first empirical jump is visible.
        ax.step([rtts[0]] + rtts, [0] + [(n + 1) / len(rtts) for n in range(len(rtts))],
                where="post", color=BLUE)
    else:
        ax.text(0.5, 0.5, "No replies: empirical CDF is undefined", ha="center", transform=ax.transAxes)
    ax.set(title=f"{title}: empirical RTT CDF", xlabel="RTT (ms)", ylabel="Fraction <= RTT", ylim=(0, 1.02))
    ax.grid(alpha=0.2)
    save_figure(fig, output, "rtt-cdf")

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 4.4), sharex=True, sharey=True, layout="constrained")
    for ax, state, color, baseline in zip(axes, ["success", "loss"], [BLUE, ORANGE],
                                        [stats["delivery_rate"], 1 - stats["delivery_rate"]]):
        rows = stats["conditional"]
        valid = [row for row in rows if row[state + "_probability"] is not None]
        ax.bar([row["lag"] for row in valid], [row[state + "_probability"] for row in valid], color=color)
        ax.axhline(baseline, color="#303b4b", linestyle="--", linewidth=1,
                   label=f"Unconditional {state}: {baseline:.2%}")
        ax.set(ylabel=f"P({state} N+k | {state} N)", ylim=(0, 1.06))
        ax.legend(loc="lower right" if state == "success" else "upper right", fontsize=8)
        if not valid:
            ax.text(0.5, 0.5, f"No {state} anchors: conditional probability undefined",
                    ha="center", fontsize=9, transform=ax.transAxes)
    axes[0].set_title(f"{title}: conditional delivery and loss")
    axes[1].set(xlabel="Sequence offset k (one step is approximately 0.2 seconds)", xticks=list(range(-10, 11, 2)))
    save_figure(fig, output, "conditional")

    pairs = adjacent_pairs(measurement)
    fig, ax = plt.subplots(figsize=(7.4, 3.5), layout="constrained")
    if pairs:
        ax.scatter(*zip(*pairs), s=5, alpha=0.3, color=BLUE, rasterized=True)
    pearson = stats["adjacent_rtt_pearson"]
    label = f"Pearson r = {pearson:.3f}" if pearson is not None else "Pearson r undefined"
    ax.set(title=textwrap.fill(f"{title}: consecutive successful probes ({label})", width=75),
           xlabel="RTT of sequence N (ms)", ylabel="RTT of sequence N+1 (ms)")
    ax.grid(alpha=0.2)
    save_figure(fig, output, "adjacent-rtt")


def plot_rates(trials, title, output):
    fig, ax = plt.subplots(figsize=(7.4, 3.0), layout="constrained")
    x = [trial["observed_request_payload_bps"] / 1000 for trial in trials]
    y = [trial["observed_reply_payload_bps"] / 1000 for trial in trials]
    ax.plot(x, y, "o-", color=BLUE, label="Observed ICMP payload reply rate")
    maximum = max(x, default=1)
    ax.plot([0, maximum], [0, maximum], "--", color="#777777", label="Equal request/reply rate")
    ax.set(title=f"{title}: bounded ICMP rate trials", xlabel="Sent payload / total trial time (kbit/s)",
           ylabel="Reply payload / total trial time (kbit/s)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    save_figure(fig, output, "rate-trials")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", action="store_true", help="Explicitly allow incomplete logs; results are provisional")
    args = parser.parse_args()
    raw = (args.data / "ping.txt").read_bytes()
    metadata = json.loads((args.data / "metadata.json").read_text(encoding="utf-8"))
    measurement = parse_ping(raw.decode("utf-8"), allow_partial=args.preview)
    if not args.preview and metadata["state"] != "finished":
        raise ValueError("Metadata is not finished; do not publish a final report yet")
    stats = summarize(measurement)
    stats.update(host=metadata["host"], source_sha256=hashlib.sha256(raw).hexdigest(),
                 started_utc=metadata["started_utc"], ended_utc=metadata.get("ended_utc"),
                 elapsed_s=metadata.get("elapsed_s"), interval_s=metadata["interval_s"],
                 payload_bytes=metadata["payload_bytes"], collection_state=metadata["state"])
    burst_path = args.data / "bursts/trials.json"
    stats["burst_trials"] = json.loads(burst_path.read_text(encoding="utf-8")) if burst_path.exists() else []
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "statistics.json").write_text(json.dumps(stats, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (args.output / "probes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sequence", "received", "reply_unix_seconds", "rtt_ms", "rtt_is_upper_bound"])
        for sequence in range(1, measurement.sent + 1):
            reply = measurement.replies.get(sequence)
            writer.writerow([sequence, int(reply is not None), reply.timestamp if reply else "",
                             reply.rtt_ms if reply else "", int(reply.upper_bound) if reply else ""])
    with (args.output / "conditional.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(stats["conditional"][0]))
        writer.writeheader()
        writer.writerows(stats["conditional"])
    plot_path(measurement, stats, metadata, args.output)
    if stats["burst_trials"]:
        plot_rates(stats["burst_trials"], metadata["host"], args.output)
    print(json.dumps({key: value for key, value in stats.items() if key not in ("conditional", "burst_trials")}, indent=2))


if __name__ == "__main__":
    main()
