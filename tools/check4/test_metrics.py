"""Deterministic parser/statistics regression tests; not measured experiment data."""

import unittest

from metrics import adjacent_pairs, conditional_rates, parse_ping, summarize


def log(sequences, sent, *, received=None):
    lines = [f"[1700000000.{n:06d}] 64 bytes from 192.0.2.1: icmp_seq={n} ttl=64 time={n}.0 ms"
             for n in sequences]
    received = len(set(sequences)) if received is None else received
    return "\n".join(lines + [f"{sent} packets transmitted, {received} received, 0% packet loss"])


class MetricsTest(unittest.TestCase):
    def test_leading_internal_and_trailing_losses(self):
        m = parse_ping(log([2, 3, 6], 8))
        s = summarize(m)
        self.assertEqual((s["sent"], s["lost"], s["longest_success_run"], s["longest_loss_run"]),
                         (8, 5, 2, 2))
        self.assertEqual(s["delivery_rate"], 3 / 8)

    def test_duplicates_and_reordering(self):
        m = parse_ping(log([3, 1, 3, 2], 3))
        self.assertEqual((len(m.replies), m.duplicates), (3, 1))
        self.assertEqual(summarize(m)["lost"], 0)

    def test_outstanding_notice_is_not_final_loss(self):
        m = parse_ping("[1700000000.0] no answer yet for icmp_seq=1\n" + log([1, 2], 2))
        self.assertEqual(summarize(m)["delivery_rate"], 1)

    def test_no_loss_condition_is_undefined(self):
        c = conditional_rates([True] * 5, 0)
        self.assertEqual(c["success_probability"], 1)
        self.assertIsNone(c["loss_probability"])
        self.assertEqual(c["loss_denominator"], 0)

    def test_lag_edges_and_denominators(self):
        flags = [True, False, False, True]
        plus, minus = conditional_rates(flags, 1), conditional_rates(flags, -1)
        self.assertEqual(plus["loss_probability"], 0.5)
        self.assertEqual(minus["loss_probability"], 0.5)
        self.assertEqual(plus["success_denominator"], 1)
        self.assertIsNone(conditional_rates(flags, 10)["success_probability"])

    def test_no_pair_across_missing_sequence(self):
        self.assertEqual(adjacent_pairs(parse_ping(log([1, 3, 4], 4))), [(3.0, 4.0)])

    def test_all_loss_and_single_success(self):
        s = summarize(parse_ping(log([], 4)))
        self.assertEqual(s["longest_loss_run"], 4)
        self.assertIsNone(s["rtt_min_ms"])
        self.assertIsNone(s["adjacent_rtt_pearson"])
        self.assertIsNone(summarize(parse_ping(log([2], 4)))["adjacent_rtt_pearson"])

    def test_incomplete_and_inconsistent_log_rejected(self):
        with self.assertRaises(ValueError):
            parse_ping("[1700000000.0] no answer yet for icmp_seq=3")
        with self.assertRaises(ValueError):
            parse_ping(log([1], 4, received=2))
        with self.assertRaises(ValueError):
            parse_ping(log([5], 4))

    def test_preview_is_explicitly_nonfinal(self):
        m = parse_ping("[1700000000.0] no answer yet for icmp_seq=3", allow_partial=True)
        self.assertFalse(m.finalized)
        self.assertEqual(m.sent, 3)

    def test_less_than_one_ms_is_labelled_upper_bound(self):
        text = "[1700000000.0] 64 bytes from 192.0.2.1: icmp_seq=1 ttl=64 time<1 ms\n"
        text += "1 packets transmitted, 1 received, 0% packet loss"
        s = summarize(parse_ping(text))
        self.assertEqual(s["rtt_upper_bound_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
