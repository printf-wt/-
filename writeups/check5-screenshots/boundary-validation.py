"""Exercise exact expiry, malformed frames, large ticks and synchronous ARP on loopback objects."""

from pathlib import Path
import subprocess
import tempfile


SOURCE = r'''
#include "network_interface.hh"
#include "arp_message.hh"
#include "helpers.hh"

#include <iostream>
#include <limits>
#include <stdexcept>

using namespace std;

void require(bool condition, const string& label) {
  if (!condition) throw runtime_error(label);
}

const EthernetAddress local {2, 0, 0, 0, 0, 1};
const EthernetAddress remote {2, 0, 0, 0, 0, 2};
const EthernetAddress changed {2, 0, 0, 0, 0, 3};
const Address self {"10.0.0.1", 0};
const Address hop {"10.0.0.2", 0};

struct Port : NetworkInterface::OutputPort {
  vector<EthernetFrame> frames {};
  NetworkInterface* peer {};
  void transmit(const NetworkInterface&, const EthernetFrame& frame) override {
    frames.push_back(clone(frame));
    if (peer) peer->recv_frame(clone(frame));
  }
};

InternetDatagram datagram(const string& payload = "new") {
  InternetDatagram d;
  d.header.src = self.ipv4_numeric();
  d.header.dst = Address {"8.8.8.8", 0}.ipv4_numeric();
  d.payload.emplace_back(string(payload));
  d.header.len = d.header.hlen * 4 + payload.size();
  d.header.compute_checksum();
  return d;
}

EthernetFrame advertisement(const EthernetAddress& mac = remote) {
  ARPMessage arp;
  arp.opcode = ARPMessage::OPCODE_REPLY;
  arp.sender_ip_address = hop.ipv4_numeric();
  arp.sender_ethernet_address = mac;
  arp.target_ip_address = self.ipv4_numeric();
  arp.target_ethernet_address = local;
  return {{local, mac, EthernetHeader::TYPE_ARP}, serialize(arp)};
}

struct Fixture {
  shared_ptr<Port> port {make_shared<Port>()};
  NetworkInterface nic {"boundary", port, local, self};
};

void exact_pending_expiry() {
  Fixture f;
  f.nic.send_datagram(datagram("old1"), hop);
  f.nic.tick(4999);
  f.nic.send_datagram(datagram("old2"), hop);
  require(f.port->frames.size() == 1, "request suppressed through 4999ms");
  f.nic.tick(1);
  require(f.port->frames.size() == 1, "tick must not proactively resend ARP");
  f.nic.recv_frame(advertisement());
  require(f.port->frames.size() == 1, "expired queue cannot revive on late ARP");
  f.nic.send_datagram(datagram(), hop);
  require(f.port->frames.size() == 2 && f.port->frames.back().header.dst == remote,
          "late mapping still learns and sends new traffic");
  InternetDatagram received;
  require(parse(received, f.port->frames.back().payload)
          && received.header.dst == Address {"8.8.8.8", 0}.ipv4_numeric()
          && concat(received.payload) == "new", "Ethernet next hop must not overwrite final IP destination");
}

void exact_cache_expiry_and_refresh() {
  Fixture f;
  f.nic.recv_frame(advertisement());
  f.nic.tick(29999);
  f.nic.send_datagram(datagram(), hop);
  require(f.port->frames.back().header.type == EthernetHeader::TYPE_IPv4, "cache valid at 29999ms");
  f.nic.recv_frame(advertisement(changed));
  f.nic.tick(1);
  f.nic.send_datagram(datagram(), hop);
  require(f.port->frames.back().header.dst == changed, "refresh uses new MAC and full lifetime");
  f.nic.tick(29999);
  f.nic.send_datagram(datagram(), hop);
  require(f.port->frames.back().header.type == EthernetHeader::TYPE_ARP, "cache expires at exactly 30000ms");
}

void huge_tick() {
  Fixture f;
  f.nic.recv_frame(advertisement());
  const Address other {"10.0.0.3", 0};
  f.nic.send_datagram(datagram("old"), other);
  f.nic.tick(numeric_limits<size_t>::max());
  require(f.port->frames.size() == 1, "huge tick does not generate traffic");
  f.nic.send_datagram(datagram(), hop);
  require(f.port->frames.size() == 2 && f.port->frames.back().header.type == EthernetHeader::TYPE_ARP,
          "huge tick expires cache without integer wrap");
  f.nic.recv_frame(advertisement());
  require(f.port->frames.size() == 3, "newly queued traffic delivered once");
}

void malformed_frames() {
  Fixture f;
  auto frame = advertisement();
  frame.payload.clear();
  frame.payload.emplace_back("x");
  f.nic.recv_frame(clone(frame));
  frame.header.type = EthernetHeader::TYPE_IPv4;
  f.nic.recv_frame(clone(frame));
  frame = advertisement();
  frame.header.dst = changed;
  f.nic.recv_frame(clone(frame));
  frame = advertisement();
  frame.header.type = 0x86dd;
  f.nic.recv_frame(clone(frame));
  require(f.nic.datagrams_received().empty() && f.port->frames.empty(), "invalid/foreign/unknown frames ignored");
  f.nic.send_datagram(datagram(), hop);
  require(f.port->frames.size() == 1 && f.port->frames[0].header.type == EthernetHeader::TYPE_ARP,
          "invalid frames cannot populate cache");
  f.nic.recv_frame(advertisement());
  require(f.port->frames.size() == 2, "valid reply still releases pending traffic");
}

void synchronous_link() {
  auto a_port = make_shared<Port>();
  auto b_port = make_shared<Port>();
  NetworkInterface a {"A", a_port, local, self};
  NetworkInterface b {"B", b_port, remote, hop};
  a_port->peer = &b;
  b_port->peer = &a;
  a.send_datagram(datagram("first"), hop);
  a.send_datagram(datagram("second"), hop);
  require(b.datagrams_received().size() == 2, "synchronous ARP resolves during send callback");
  require(concat(b.datagrams_received().front().payload) == "first", "FIFO first payload");
  b.datagrams_received().pop();
  require(concat(b.datagrams_received().front().payload) == "second", "FIFO second payload");
  require(a_port->frames.size() == 3 && b_port->frames.size() == 1,
          "one broadcast request, one reply, two IPv4 frames");
}

int main() {
  try {
    exact_pending_expiry(); cout << "[PASS] exact 5000ms pending expiry, late reply and final IP preservation\n";
    exact_cache_expiry_and_refresh(); cout << "[PASS] exact 30000ms cache expiry and changed-MAC refresh\n";
    huge_tick(); cout << "[PASS] SIZE_MAX tick without overflow or unsolicited retransmission\n";
    malformed_frames(); cout << "[PASS] malformed, foreign and unknown Ethernet frames\n";
    synchronous_link(); cout << "[PASS] synchronous two-interface ARP and FIFO IPv4 delivery\n";
    cout << "5 supplementary scenarios passed with ASan/UBSan.\n";
  } catch (const exception& e) {
    cerr << "[FAIL] " << e.what() << '\n'; return 1;
  }
}
'''


def main():
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="check5-boundary-") as directory:
        source = Path(directory) / "boundaries.cc"
        binary = Path(directory) / "boundaries"
        source.write_text(SOURCE, encoding="utf-8")
        subprocess.run([
            "g++", "-std=c++23", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
            "-I", str(root / "src"), "-I", str(root / "util"), str(source),
            str(root / "src/network_interface.cc"), str(root / "build/wsl/util/libutil_sanitized.a"),
            "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
