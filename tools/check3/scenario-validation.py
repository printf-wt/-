"""Run deterministic sender/receiver scenarios with ASan and UBSan in Ubuntu."""

from pathlib import Path
import subprocess
import tempfile


SOURCE = r'''
#include "tcp_sender.hh"
#include "tcp_receiver.hh"

#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

void require(bool value, const string& label)
{
  if (!value) throw runtime_error(label);
}

struct Link {
  TCPSender sender {ByteStream {8192}, Wrap32 {100}, 10};
  vector<TCPSenderMessage> packets {};
  TCPSender::TransmitFunction transmit = [this](const TCPSenderMessage& message) {
    packets.push_back(message);
  };
  void connect(uint16_t window) {
    sender.push(transmit);
    require(packets.size() == 1 && packets[0].SYN, "initial SYN");
    sender.receive({Wrap32 {101}, window, false});
    packets.clear();
  }
};

void loss_and_lost_ack()
{
  Link link;
  TCPReceiver receiver {Reassembler {ByteStream {8}}};
  link.sender.writer().push("ABCDEF");
  link.sender.writer().close();
  link.sender.push(link.transmit);
  receiver.receive(link.packets.back());
  link.sender.receive(receiver.send());
  link.packets.clear();
  link.sender.push(link.transmit);
  require(link.packets.size() == 1 && link.packets[0].FIN, "data plus FIN");
  link.sender.tick(9, link.transmit);
  require(link.packets.size() == 1, "no early retransmission");
  // Drop the first data packet, then deliver its retransmission.
  link.sender.tick(1, link.transmit);
  require(link.packets.size() == 2, "retransmit after lost data");
  receiver.receive(link.packets.back());
  // Drop the receiver's ACK; the duplicate must not duplicate output.
  link.sender.tick(20, link.transmit);
  require(link.packets.size() == 3, "backoff retransmission after lost ACK");
  receiver.receive(link.packets.back());
  require(receiver.send().ackno == Wrap32 {108}, "cumulative ACK including FIN");
  string output;
  read(receiver.reader(), 6, output);
  require(output == "ABCDEF" && receiver.reader().is_finished(), "exactly-once delivery");
  link.sender.receive(receiver.send());
  require(link.sender.sequence_numbers_in_flight() == 0, "ACK clears flight");
  link.sender.tick(1000, link.transmit);
  require(link.packets.size() == 3, "timer stops after ACK");
}

void zero_window()
{
  Link link;
  link.connect(0);
  link.sender.writer().push("AB");
  link.sender.writer().close();
  link.sender.push(link.transmit);
  require(link.packets.size() == 1 && link.packets[0].payload == "A", "one-byte probe");
  for (size_t i = 0; i < 3; ++i) {
    link.sender.tick(9, link.transmit);
    require(link.packets.size() == i + 1, "zero-window timer not early");
    link.sender.tick(1, link.transmit);
    require(link.packets.size() == i + 2, "zero-window constant RTO");
    require(link.sender.consecutive_retransmissions() == 0, "probes do not count as failures");
  }
  link.sender.receive({Wrap32 {102}, 2, false});
  link.sender.push(link.transmit);
  require(link.packets.back().payload == "B" && link.packets.back().FIN, "window reopens");
  link.sender.receive({Wrap32 {104}, 2, false});
  require(link.sender.sequence_numbers_in_flight() == 0, "probe recovery completes");
}

void partial_and_duplicate_ack()
{
  Link link;
  link.connect(4);
  link.sender.writer().push("abcd");
  link.sender.push(link.transmit);
  link.sender.receive({Wrap32 {103}, 4, false});
  require(link.sender.sequence_numbers_in_flight() == 2, "partial ACK advances flight");
  link.sender.tick(5, link.transmit);
  link.sender.receive({Wrap32 {103}, 4, false});
  link.sender.tick(5, link.transmit);
  require(link.packets.size() == 2 && link.packets.back().payload == "abcd"
          && link.packets.back().seqno == Wrap32 {101}, "duplicate ACK does not delay intact retransmission");
  link.sender.receive({Wrap32 {105}, 4, false});
  link.sender.tick(1000, link.transmit);
  require(link.packets.size() == 2 && link.sender.consecutive_retransmissions() == 0,
          "valid ACK resets retry counter and stops timer");
}

void large_timer()
{
  constexpr uint64_t maximum = numeric_limits<uint64_t>::max();
  TCPSender sender {ByteStream {1}, Wrap32 {0}, maximum - 1};
  vector<TCPSenderMessage> packets;
  auto transmit = [&](const TCPSenderMessage& message) { packets.push_back(message); };
  sender.push(transmit);
  sender.tick(maximum - 2, transmit);
  require(packets.size() == 1, "large timer before expiry");
  sender.tick(1, transmit);
  require(packets.size() == 2, "large first expiry");
  sender.tick(maximum - 1, transmit);
  require(packets.size() == 2, "saturated RTO does not wrap");
  sender.tick(1, transmit);
  require(packets.size() == 3 && sender.consecutive_retransmissions() == 2, "large second expiry");
}

void impossible_ack()
{
  Link link;
  link.connect(4);
  link.sender.writer().push("abcdefgh");
  link.sender.push(link.transmit);
  link.sender.tick(10, link.transmit);
  link.sender.receive({Wrap32 {200}, 65535, false});
  link.sender.push(link.transmit);
  require(link.packets.size() == 2 && link.sender.sequence_numbers_in_flight() == 4,
          "future ACK cannot open window or discard data");
  link.sender.tick(19, link.transmit);
  require(link.packets.size() == 2, "future ACK cannot change backed-off RTO");
  link.sender.tick(1, link.transmit);
  require(link.packets.size() == 3 && link.packets.back().payload == "abcd"
          && link.sender.consecutive_retransmissions() == 2, "future ACK cannot reset retry counter");
}

void wrap_and_reorder()
{
  const Wrap32 isn {numeric_limits<uint32_t>::max() - 1};
  TCPSender sender {ByteStream {4096}, isn, 10};
  TCPReceiver receiver {Reassembler {ByteStream {4096}}};
  vector<TCPSenderMessage> packets;
  auto transmit = [&](const TCPSenderMessage& message) { packets.push_back(message); };
  string input;
  for (size_t i = 0; i < 2500; ++i) input.push_back(static_cast<char>(i % 256));
  sender.writer().push(input);
  sender.writer().close();
  sender.push(transmit);
  receiver.receive(packets.back());
  sender.receive(receiver.send());
  packets.clear();
  sender.push(transmit);
  require(packets.size() == 3 && packets[0].payload.size() == 1000
          && packets[1].payload.size() == 1000 && packets[2].payload.size() == 500
          && packets[2].FIN, "payload segmentation");
  receiver.receive(packets[2]);
  receiver.receive(packets[1]);
  require(receiver.send().ackno == isn + 1, "out-of-order FIN waits for gap");
  receiver.receive(packets[0]);
  require(receiver.send().ackno == Wrap32 {2500}, "ACK wraps across 32-bit boundary");
  sender.receive(receiver.send());
  string output;
  read(receiver.reader(), input.size(), output);
  require(output == input && receiver.reader().is_finished()
          && sender.sequence_numbers_in_flight() == 0, "binary stream delivered after reorder");
}

int main()
{
  try {
    loss_and_lost_ack(); cout << "[PASS] lost data and lost ACK: exactly-once delivery\n";
    zero_window(); cout << "[PASS] zero-window probes and window reopening\n";
    partial_and_duplicate_ack(); cout << "[PASS] partial ACK and duplicate ACK timing\n";
    large_timer(); cout << "[PASS] UINT64 timer boundary and saturated backoff\n";
    impossible_ack(); cout << "[PASS] impossible future ACK rejected\n";
    wrap_and_reorder(); cout << "[PASS] 2500 binary bytes, sequence wrap and reverse delivery\n";
    cout << "6 supplementary scenarios passed with ASan/UBSan.\n";
  } catch (const exception& error) {
    cerr << "[FAIL] " << error.what() << '\n';
    return 1;
  }
}
'''


def main():
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="check3-scenarios-") as directory:
        source = Path(directory) / "scenarios.cc"
        binary = Path(directory) / "scenarios"
        source.write_text(SOURCE, encoding="utf-8")
        sources = ["byte_stream.cc", "byte_stream_helpers.cc", "reassembler.cc",
                   "wrapping_integers.cc", "tcp_receiver.cc", "tcp_sender.cc"]
        subprocess.run(
            ["g++", "-std=c++23", "-O1", "-fsanitize=address,undefined",
             "-fno-sanitize-recover=all", "-I", str(root / "src"), "-I", str(root / "util"),
             str(source), *(str(root / "src" / name) for name in sources), "-o", str(binary)],
            check=True,
        )
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
