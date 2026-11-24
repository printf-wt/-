"""Parse Linux iputils ping logs and compute sequence-aware path statistics."""

from dataclasses import dataclass
import math
import re
import statistics


REPLY = re.compile(r"^\[(\d+(?:\.\d+)?)\].*?icmp_seq=(\d+).*?time([=<])([\d.]+)\s*ms")
SUMMARY = re.compile(r"(\d+) packets transmitted,\s*(\d+)(?: packets)? received")
SEQUENCE = re.compile(r"icmp_seq[= ](\d+)")


@dataclass(frozen=True)
class Reply:
    sequence: int
    timestamp: float
    rtt_ms: float
    upper_bound: bool = False


@dataclass
class Measurement:
    sent: int
    replies: dict[int, Reply]
    duplicates: int
    finalized: bool


def parse_ping(text: str, *, allow_partial: bool = False) -> Measurement:
    """Use the final sent count, including leading and trailing missing replies.

    A delayed reply supersedes an earlier '-O' outstanding notice. Duplicate
    replies do not inflate delivery; the first observed reply supplies the RTT.
    A time< value is retained as an upper bound and explicitly counted later.
    """
    replies = {}
    duplicates = 0
    for line in text.splitlines():
        match = REPLY.search(line)
        if not match:
            continue
        timestamp, sequence, comparator, rtt = match.groups()
        reply = Reply(int(sequence), float(timestamp), float(rtt), comparator == "<")
        if reply.sequence in replies:
            duplicates += 1
        else:
            replies[reply.sequence] = reply
    summaries = list(SUMMARY.finditer(text))
    finalized = bool(summaries)
    if finalized:
        sent, received = map(int, summaries[-1].groups())
        if received != len(replies):
            raise ValueError(f"Summary received {received}, parsed unique replies {len(replies)}")
    elif allow_partial:
        sent = max((int(n) for n in SEQUENCE.findall(text)), default=0)
    else:
        raise ValueError("No final ping summary: collection is running or the log is incomplete")
    if sent < 1 or sent >= 65536:
        raise ValueError("Expected 1..65535 sent probes (ICMP sequence wrap is not supported)")
    if any(n < 1 or n > sent for n in replies):
        raise ValueError("Reply sequence is outside the transmitted range")
    if any(not math.isfinite(r.rtt_ms) or r.rtt_ms < 0 for r in replies.values()):
        raise ValueError("Invalid RTT")
    return Measurement(sent, replies, duplicates, finalized)


def longest_run(values, target):
    best = current = 0
    for value in values:
        current = current + 1 if value == target else 0
        best = max(best, current)
    return best


def conditional_rates(success, lag):
    """P(S[N+k]=state | S[N]=state), using only in-range pairs.

    Missing conditioning states have no defined probability (None, never zero).
    The central k=0 bar is one whenever its conditioning state exists.
    """
    start = max(0, -lag)
    stop = min(len(success), len(success) - lag)
    result = {"lag": lag}
    for state, name in [(True, "success"), (False, "loss")]:
        anchors = [n for n in range(start, stop) if success[n] == state]
        hits = sum(success[n + lag] == state for n in anchors)
        result[name + "_denominator"] = len(anchors)
        result[name + "_probability"] = hits / len(anchors) if anchors else None
    return result


def adjacent_pairs(measurement):
    """Only pair actual consecutive sequence numbers, never bridge a loss."""
    return [(measurement.replies[n].rtt_ms, measurement.replies[n + 1].rtt_ms)
            for n in range(1, measurement.sent)
            if n in measurement.replies and n + 1 in measurement.replies]


def correlation(pairs):
    if len(pairs) < 2:
        return None
    x, y = zip(*pairs)
    if max(x) == min(x) or max(y) == min(y):
        return None
    return statistics.correlation(x, y)


def quantile(sorted_values, fraction):
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def summarize(measurement):
    success = [n in measurement.replies for n in range(1, measurement.sent + 1)]
    rtts = sorted(reply.rtt_ms for reply in measurement.replies.values())
    pairs = adjacent_pairs(measurement)
    return {
        "finalized": measurement.finalized, "sent": measurement.sent,
        "received_unique": len(rtts), "duplicates": measurement.duplicates,
        "lost": measurement.sent - len(rtts), "delivery_rate": len(rtts) / measurement.sent,
        "longest_success_run": longest_run(success, True),
        "longest_loss_run": longest_run(success, False),
        "rtt_min_ms": min(rtts) if rtts else None,
        "rtt_max_ms": max(rtts) if rtts else None,
        "rtt_mean_ms": statistics.mean(rtts) if rtts else None,
        "rtt_median_ms": statistics.median(rtts) if rtts else None,
        "rtt_p95_ms": quantile(rtts, 0.95),
        "rtt_upper_bound_count": sum(r.upper_bound for r in measurement.replies.values()),
        "adjacent_rtt_pairs": len(pairs), "adjacent_rtt_pearson": correlation(pairs),
        "conditional": [conditional_rates(success, lag) for lag in range(-10, 11)],
    }
