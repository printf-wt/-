"""Run the real CS144 endpoints and routers over loopback UDP; retain honest evidence."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import selectors
import socket
import struct
import subprocess
import sys
import threading
import time


def packet_info(frame):
    """Decode only headers needed for evidence; the C++ stack handles the protocol."""
    info = {"bytes": len(frame)}
    if len(frame) < 14:
        return info
    kind = struct.unpack_from("!H", frame, 12)[0]
    info["type"] = {0x0806: "ARP", 0x0800: "IPv4"}.get(kind, hex(kind))
    if kind == 0x0806 and len(frame) >= 42:
        info.update(opcode=struct.unpack_from("!H", frame, 20)[0],
                    sender=socket.inet_ntoa(frame[28:32]), target=socket.inet_ntoa(frame[38:42]))
    if kind == 0x0800 and len(frame) >= 34:
        ihl = (frame[14] & 15) * 4
        total = struct.unpack_from("!H", frame, 16)[0]
        info.update(src=socket.inet_ntoa(frame[26:30]), dst=socket.inet_ntoa(frame[30:34]), ttl=frame[22])
        start = 14 + ihl
        if frame[23] == 6 and len(frame) >= start + 20:
            source, dest, seq, ack = struct.unpack_from("!HHII", frame, start)
            tcp_len = (frame[start + 12] >> 4) * 4
            info.update(sport=source, dport=dest, seq=seq, ack=ack, flags=frame[start + 13],
                        payload_bytes=max(0, total - ihl - tcp_len))
    return info


class Tunnel:
    """A UDP relay observes Ethernet frames without implementing TCP or IP routing."""

    def __init__(self, name, left, right, output, drop_first_data=False):
        self.name, self.left, self.right = name, left, right
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.port = self.socket.getsockname()[1]
        self.drop_first_data = drop_first_data
        self.dropped = 0
        self.count = 0
        self.types = {}
        self.ttls = {}
        self.events = []
        self.seen_data = set()
        self.repeated_data = 0
        self.capture = (output / (name + ".pcap")).open("wb")
        # Classic pcap, little endian, Ethernet link type, first 96 bytes of each frame.
        self.capture.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 96, 1))

    def forward(self):
        frame, address = self.socket.recvfrom(65535)
        if address[0] != "127.0.0.1" or address[1] not in (self.left, self.right):
            raise RuntimeError("unexpected relay sender")
        direction = "left-to-right" if address[1] == self.left else "right-to-left"
        peer = self.right if address[1] == self.left else self.left
        info = packet_info(frame)
        self.count += 1
        key = info.get("type", "unknown")
        self.types[key] = self.types.get(key, 0) + 1
        if "ttl" in info:
            key = str(info["ttl"])
            self.ttls[key] = self.ttls.get(key, 0) + 1
        if info.get("payload_bytes", 0):
            key = (direction, info["sport"], info["dport"], info["seq"], info["payload_bytes"])
            if key in self.seen_data:
                self.repeated_data += 1
            self.seen_data.add(key)
        dropped = bool(self.drop_first_data and not self.dropped and info.get("payload_bytes", 0))
        if dropped:
            self.dropped += 1
        now = time.time_ns()
        snap = frame[:96]
        self.capture.write(struct.pack("<IIII", now // 1_000_000_000, now % 1_000_000_000 // 1000,
                                       len(snap), len(frame)) + snap)
        if len(self.events) < 24 or dropped:
            self.events.append({"direction": direction, "dropped": dropped, **info})
        if not dropped:
            self.socket.sendto(frame, ("127.0.0.1", peer))

    def summary(self):
        return {"name": self.name, "proxy_port": self.port, "left_port": self.left,
                "right_port": self.right, "frames": self.count, "types": self.types,
                "ttls": self.ttls, "dropped_data_frames": self.dropped,
                "repeated_data_ranges": self.repeated_data, "first_events": self.events,
                "capture": self.name + ".pcap", "snaplen": 96}

    def close(self):
        self.capture.close()
        self.socket.close()


def allocate_ports(count):
    held = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", 0))
            held.append(sock)
        return [sock.getsockname()[1] for sock in held]
    finally:
        for sock in held:
            sock.close()


def run(args):
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    build = (root / args.build).resolve()
    suffix = "_sanitized" if args.sanitized else ""
    endpoint = build / "apps" / ("tcp_eth_udp" + suffix)
    router_app = build / "apps" / ("fun_router" + suffix)
    for program in (endpoint, router_app):
        if not program.is_file():
            raise FileNotFoundError(program)
    ports = iter(allocate_ports(20))
    tunnels, routers, endpoints = [], {}, {}

    def router(name):
        routers[name] = {"interfaces": [], "routes": []}

    def link(name, left, right):
        """Ends are router/interface/IP triples, or endpoint/IP/gateway triples."""
        lp, rp = next(ports), next(ports)
        tunnel = Tunnel(name, lp, rp, output, args.drop_first_data and not tunnels)
        tunnels.append(tunnel)
        for end, local in ((left, lp), (right, rp)):
            node, interface, address = end
            if node in routers:
                routers[node]["interfaces"].append(
                    f"interface:{interface}:{address}:{local}:127.0.0.1:{tunnel.port}")
            else:
                endpoints[node] = {"port": local, "proxy": tunnel.port, "ip": interface, "gateway": address}

    if args.topology == "tiny":
        router("R1")
        link("stanford", ("S1", "50.9.8.7", "50.0.0.1"), ("R1", "stanford", "50.0.0.1"))
        link("ucla", ("C1", "80.6.5.4", "80.0.0.1"), ("R1", "ucla", "80.0.0.1"))
        routers["R1"]["routes"] = ["route:50.0.0.0:8:stanford", "route:80.0.0.0:8:ucla"]
        flows = [("C1", "S1")]
    else:
        for name in ("R1", "R2", "R3"):
            router(name)
        link("client1", ("C1", "80.6.5.4", "80.0.0.1"), ("R1", "client1", "80.0.0.1"))
        link("client2", ("C2", "81.6.5.4", "81.0.0.1"), ("R1", "client2", "81.0.0.1"))
        link("r1-r2", ("R1", "east", "10.0.12.1"), ("R2", "west", "10.0.12.2"))
        link("r2-r3", ("R2", "east", "10.0.23.2"), ("R3", "west", "10.0.23.3"))
        link("server1", ("S1", "50.9.8.7", "50.0.0.1"), ("R3", "server1", "50.0.0.1"))
        link("server2", ("S2", "51.9.8.7", "51.0.0.1"), ("R3", "server2", "51.0.0.1"))
        routers["R1"]["routes"] = ["route:80.0.0.0:8:client1", "route:81.0.0.0:8:client2"] + [
            f"route:{net}.0.0.0:8:east:10.0.12.2" for net in (50, 51)]
        routers["R2"]["routes"] = [f"route:{net}.0.0.0:8:west:10.0.12.1" for net in (80, 81)] + [
            f"route:{net}.0.0.0:8:east:10.0.23.3" for net in (50, 51)]
        routers["R3"]["routes"] = ["route:50.0.0.0:8:server1", "route:51.0.0.0:8:server2"] + [
            f"route:{net}.0.0.0:8:west:10.0.23.2" for net in (80, 81)]
        flows = [("C1", "S1"), ("C2", "S2")]

    stop = threading.Event()
    relay_errors = []

    def relay_loop():
        try:
            with selectors.DefaultSelector() as selector:
                for tunnel in tunnels:
                    selector.register(tunnel.socket, selectors.EVENT_READ, tunnel)
                while not stop.is_set():
                    for item, _ in selector.select(0.05):
                        item.data.forward()
        except Exception as error:
            relay_errors.append(str(error))

    thread = threading.Thread(target=relay_loop, daemon=True)
    processes, streams, commands, results = [], [], {}, []
    started = time.monotonic()
    report = {"status": "failed", "started_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "single WSL instance; real UDP sockets and separate C++ processes",
              "topology": args.topology, "sanitized": args.sanitized, "bytes_per_direction": args.size,
              "routers": routers, "endpoints": endpoints, "flows": flows}

    def start(name, command, piped=False):
        if args.chat and piped:
            command = [sys.executable, root / "tools/check7/chat.py", "--name", name,
                       "--downloads", output / (name + "-downloads"), "--", *command]
        log = (output / (name + ".stderr.log")).open("wb")
        streams.append(log)
        process = subprocess.Popen([str(item) for item in command], cwd=root,
                                   stdin=subprocess.PIPE if piped else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE if piped else subprocess.DEVNULL, stderr=log)
        processes.append((name, process))
        commands[name] = [str(item) for item in command]
        return process

    def exchange(name, process, data, expected):
        chat_expected = None
        if args.chat:
            attachment = output / (name + ".sent.bin")
            attachment.write_bytes(data)
            data = ("Hello from " + name + "\n/send " + str(attachment) + "\n/quit\n").encode()
            chat_expected = hashlib.sha256(expected).hexdigest()
        received, _ = process.communicate(data, timeout=args.timeout)
        if args.chat:
            (output / (name + ".chat.log")).write_bytes(received)
            receipts = json.loads((output / (name + "-downloads/receipts.json")).read_text(encoding="utf-8"))
            files = receipts["files"]
            peer = next(server if name == client else client for client, server in flows if name in (client, server))
            matched_chat = receipts["chats"] == [{"from": peer, "text": "Hello from " + peer}]
            matched_file = len(files) == 1 and files[0]["sha256"] == chat_expected and files[0]["size"] == len(expected)
            if matched_file:
                path = output / (name + "-downloads") / files[0]["saved_as"]
                matched_file = path.read_bytes() == expected
            return {"node": name, "returncode": process.returncode, "received_bytes": len(expected),
                    "expected_bytes": len(expected), "sha256": files[0]["sha256"] if files else None,
                    "expected_sha256": chat_expected, "chat_match": matched_chat,
                    "match": process.returncode == 0 and matched_chat and matched_file}
        actual_hash = hashlib.sha256(received).hexdigest()
        expected_hash = hashlib.sha256(expected).hexdigest()
        result = {"node": name, "returncode": process.returncode, "received_bytes": len(received),
                  "expected_bytes": len(expected), "sha256": actual_hash, "expected_sha256": expected_hash,
                  "match": process.returncode == 0 and received == expected}
        if args.save_payloads:
            (output / (name + ".received.bin")).write_bytes(received)
        return result

    try:
        thread.start()
        for name, config in routers.items():
            start(name, [router_app, *config["interfaces"], *config["routes"]])
        time.sleep(0.15)
        jobs = []
        for client, server in flows:
            c, s = endpoints[client], endpoints[server]
            to_server = hashlib.shake_256((client + " to " + server).encode()).digest(args.size)
            to_client = hashlib.shake_256((server + " to " + client).encode()).digest(args.size)
            sp = start(server, [endpoint, "server", s["port"], s["gateway"], s["ip"] + ":80"], True)
            time.sleep(0.1)
            cp = start(client, [endpoint, "client", c["port"], f"127.0.0.1:{c['proxy']}",
                                c["gateway"], c["ip"], s["ip"] + ":80"], True)
            jobs.extend([(server, sp, to_client, to_server), (client, cp, to_server, to_client)])
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = [pool.submit(exchange, *job) for job in jobs]
            try:
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    print(json.dumps(result), flush=True)
            except Exception:
                for _, process in processes:
                    if process.poll() is None:
                        process.kill()
                raise
        if relay_errors:
            raise RuntimeError(relay_errors)
        if not all(result["match"] for result in results):
            raise RuntimeError("payload or process verification failed")
        if args.drop_first_data and not any(tunnel.dropped and tunnel.repeated_data for tunnel in tunnels):
            raise RuntimeError("loss experiment did not observe a repeated data range")
        for name, process in processes:
            if name in routers and process.poll() is not None:
                raise RuntimeError("router exited unexpectedly: " + name)
        report["status"] = "passed"
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        for _, process in processes:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        stop.set()
        thread.join(timeout=2)
        for stream in streams:
            stream.close()
        report.update(elapsed_s=time.monotonic() - started, transfers=results, commands=commands,
                      links=[tunnel.summary() for tunnel in tunnels], relay_errors=relay_errors)
        for tunnel in tunnels:
            tunnel.close()
        (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory, never overwrite an earlier run")
    parser.add_argument("--topology", choices=["tiny", "bigger"], default="tiny")
    parser.add_argument("--build", type=Path, default=Path("build/wsl"))
    parser.add_argument("--sanitized", action="store_true")
    parser.add_argument("--drop-first-data", action="store_true")
    parser.add_argument("--size", type=int, default=1_048_576)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--save-payloads", action="store_true")
    parser.add_argument("--chat", action="store_true", help="wrap transport in the creative chat/file application")
    args = parser.parse_args()
    if args.size <= 0 or args.timeout <= 0:
        parser.error("size and timeout must be positive")
    run(args)


if __name__ == "__main__":
    main()
