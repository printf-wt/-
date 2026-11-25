"""Compile independent router scenarios with ASan/UBSan after building check6."""

from pathlib import Path
import subprocess
import tempfile


SOURCE = r'''
#include "router.hh"
#include "arp_message.hh"
#include "helpers.hh"
#include <array>
#include <iostream>
#include <random>
#include <stdexcept>
using namespace std;

void require(bool condition, const string& label) {
  if (!condition) throw runtime_error(label);
}
uint32_t ip(const string& value) { return Address{value}.ipv4_numeric(); }
const EthernetAddress remote {2, 9, 8, 7, 6, 5};
struct Port : NetworkInterface::OutputPort {
  vector<EthernetFrame> frames {};
  void transmit(const NetworkInterface&, const EthernetFrame& frame) override {
    frames.push_back(clone(frame));
  }
};
struct Fixture {
  Router router {};
  array<shared_ptr<Port>, 3> ports {};
  array<EthernetAddress, 3> macs {};
  Fixture() {
    for (size_t i = 0; i < 3; ++i) {
      ports[i] = make_shared<Port>();
      macs[i] = {2, 0, 0, 0, 0, static_cast<uint8_t>(i + 1)};
      router.add_interface(make_shared<NetworkInterface>("if" + to_string(i), ports[i], macs[i],
                           Address::from_ipv4_numeric(ip("10.0.0.1") + i)));
    }
  }
  void learn(size_t out, uint32_t address) {
    ARPMessage arp;
    arp.opcode = ARPMessage::OPCODE_REPLY;
    arp.sender_ip_address = address;
    arp.sender_ethernet_address = remote;
    router.interface(out)->recv_frame({.header = {.dst = macs[out], .src = remote,
      .type = EthernetHeader::TYPE_ARP}, .payload = serialize(arp)});
  }
  void inject(size_t in, uint32_t destination, uint8_t ttl = 64) {
    InternetDatagram d;
    d.header.src = ip("192.0.2.9");
    d.header.dst = destination;
    d.header.ttl = ttl;
    d.payload.emplace_back(string("router payload"));
    d.header.len = 20 + d.payload.back()->size();
    d.header.compute_checksum();
    const EthernetFrame frame {.header = {.dst = macs[in], .src = remote,
      .type = EthernetHeader::TYPE_IPv4}, .payload = serialize(d)};
    router.interface(in)->recv_frame(clone(frame));
  }
  InternetDatagram take(size_t out) {
    require(ports[out]->frames.size() == 1, "exactly one output frame");
    auto frame = move(ports[out]->frames.front());
    ports[out]->frames.clear();
    require(frame.header.type == EthernetHeader::TYPE_IPv4, "output is IPv4");
    require(frame.header.dst == remote && frame.header.src == macs[out], "Ethernet addresses");
    InternetDatagram d;
    require(parse(d, move(frame.payload)), "forwarded header checksum and length valid");
    require(d.header.src == ip("192.0.2.9") && concat(d.payload) == "router payload",
            "source IP and payload preserved");
    return d;
  }
  void empty() {
    for (size_t i = 0; i < 3; ++i) {
      require(ports[i]->frames.empty(), "no unexpected output");
      require(router.interface(i)->datagrams_received().empty(), "incoming queue drained");
    }
  }
};

void prefix_boundaries() {
  const uint32_t base = 0xaba5fe73;
  const auto gateway = ip("198.51.100.1");
  for (uint8_t length = 0; length <= 32; ++length) {
    Fixture f;
    f.learn(1, gateway);
    f.router.add_route(base, length, Address::from_ipv4_numeric(gateway), 1);
    f.inject(0, base, 2);
    f.router.route();
    auto d = f.take(1);
    require(d.header.dst == base && d.header.ttl == 1, "prefix match and TTL 2 to 1");
    const uint32_t other = length == 0 ? ~base : base ^ (uint32_t{1} << (32 - length));
    f.inject(2, other);
    f.router.route();
    if (length == 0) {
      d = f.take(1);
      require(d.header.dst == other, "/0 matches every destination");
    }
    f.empty();
  }
}

void randomized_oracle() {
  struct Rule { uint32_t prefix; uint8_t length; size_t out; };
  Fixture f;
  vector<Rule> rules;
  mt19937 rng {1446};
  const auto gateway = ip("198.51.100.1");
  for (size_t i = 0; i < 3; ++i) f.learn(i, gateway);
  // Place /32 before the later default, so returning the last match is incorrect.
  rules.push_back({ip("203.0.113.7"), 32, 2});
  for (size_t i = 0; i < 126; ++i)
    rules.push_back({static_cast<uint32_t>(rng()), static_cast<uint8_t>(rng() % 33), rng() % 3});
  rules.push_back({0, 0, 0});
  for (const auto& r : rules)
    f.router.add_route(r.prefix, r.length, Address::from_ipv4_numeric(gateway), r.out);
  for (size_t i = 0; i < 512; ++i) {
    const uint32_t destination = i < rules.size() ? rules[i].prefix : static_cast<uint32_t>(rng());
    const Rule* best = nullptr;
    for (const auto& r : rules) {
      // Independent arithmetic oracle: compare quotients, not the production bit mask.
      const uint64_t block_size = uint64_t{1} << (32 - r.length);
      if (destination / block_size == r.prefix / block_size && (!best || r.length > best->length))
        best = &r;
    }
    require(best != nullptr, "default guarantees a match");
    f.inject(i % 3, destination);
    f.router.route();
    const auto d = f.take(best->out);
    require(d.header.dst == destination && d.header.ttl == 63, "oracle route and unchanged destination");
    f.empty();
  }
}

void drops_and_drain() {
  Fixture f;
  const auto destination = ip("203.0.113.7");
  const auto gateway = ip("198.51.100.1");
  f.router.add_route(destination, 32, Address::from_ipv4_numeric(gateway), 1);
  f.learn(1, gateway);
  for (size_t i = 0; i < 3; ++i) {
    f.inject(i, destination, 0);
    f.inject(i, destination, 1);
    f.inject(i, ip("203.0.113.8"));
    f.inject(i, destination, 2);
  }
  f.router.route();
  require(f.ports[1]->frames.size() == 3, "only TTL=2 packets forwarded, from all inputs");
  for (auto& frame : f.ports[1]->frames) {
    InternetDatagram d;
    require(parse(d, move(frame.payload)) && d.header.ttl == 1, "TTL exactly decremented");
  }
  f.ports[1]->frames.clear();
  f.empty();
  f.router.route();
  f.empty();
  Fixture no_routes;
  no_routes.inject(0, destination);
  no_routes.router.route();
  no_routes.empty();
}

void direct_and_gateway_arp() {
  Fixture f;
  const auto direct = ip("192.0.2.55");
  const auto destination = ip("203.0.113.45");
  const auto gateway = ip("198.51.100.254");
  f.router.add_route(direct, 32, {}, 1);
  f.router.add_route(destination, 32, Address::from_ipv4_numeric(gateway), 2);
  f.inject(0, direct);
  f.inject(0, destination);
  f.router.route();
  for (size_t out = 1; out <= 2; ++out) {
    require(f.ports[out]->frames.size() == 1, "one ARP on selected interface");
    auto frame = move(f.ports[out]->frames.front());
    f.ports[out]->frames.clear();
    ARPMessage arp;
    require(frame.header.type == EthernetHeader::TYPE_ARP && parse(arp, move(frame.payload)), "valid ARP");
    require(arp.target_ip_address == (out == 1 ? direct : gateway), "correct direct/gateway ARP target");
  }
  f.learn(1, direct);
  f.learn(2, gateway);
  require(f.take(1).header.dst == direct, "direct delivery preserves final IP");
  auto d = f.take(2);
  require(d.header.dst == destination && d.header.ttl == 63, "queued gateway delivery preserves IP and TTL");
  f.empty();
}

void invalid_prefix() {
  Fixture f;
  bool rejected = false;
  try { f.router.add_route(0, 33, {}, 0); }
  catch (const invalid_argument&) { rejected = true; }
  require(rejected, "invalid length rejected before shift");
  f.inject(0, ip("203.0.113.7"));
  f.router.route();
  f.empty();
}

int main() {
  try {
    prefix_boundaries(); cout << "[PASS] all 33 prefix lengths, host bits, exact /32 and /0\n";
    randomized_oracle(); cout << "[PASS] 128 routes, 512 destinations against arithmetic LPM oracle\n";
    drops_and_drain(); cout << "[PASS] TTL 0/1/2, unmatched and empty tables, all input queues drained\n";
    direct_and_gateway_arp(); cout << "[PASS] direct/gateway ARP, queued forwarding and valid updated checksum\n";
    invalid_prefix(); cout << "[PASS] invalid /33 rejected before bit shift\n";
    cout << "5 supplementary scenarios passed with ASan/UBSan.\n";
  } catch (const exception& e) {
    cerr << "[FAIL] " << e.what() << '\n'; return 1;
  }
}
'''


def main():
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="check6-boundary-") as directory:
        source = Path(directory) / "boundaries.cc"
        binary = Path(directory) / "boundaries"
        source.write_text(SOURCE, encoding="utf-8")
        subprocess.run([
            "g++", "-std=c++23", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
            "-I", str(root / "src"), "-I", str(root / "util"), str(source),
            str(root / "src/router.cc"), str(root / "src/network_interface.cc"),
            str(root / "build/wsl/util/libutil_sanitized.a"), "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
