"""Validate saved successful runs and packet headers; write a raw-evidence hash manifest."""

import hashlib
import json
from pathlib import Path
import struct

from lab import packet_info


ROOT = Path(__file__).resolve().parents[2]


def read_capture(path):
    frames = []
    with path.open("rb") as source:
        header = source.read(24)
        assert struct.unpack("<IHHIIII", header) == (0xA1B2C3D4, 2, 4, 0, 0, 96, 1), path
        while record := source.read(16):
            seconds, microseconds, captured, original = struct.unpack("<IIII", record)
            assert seconds > 0 and microseconds < 1_000_000 and captured <= 96 and original >= captured, path
            data = source.read(captured)
            assert len(data) == captured, path
            info = packet_info(data)
            if info.get("type") == "IPv4":
                ihl = (data[14] & 15) * 4
                header_bytes = data[14:14 + ihl]
                words = struct.unpack("!" + "H" * (len(header_bytes) // 2), header_bytes)
                total = sum(words)
                while total >> 16:
                    total = (total & 0xffff) + (total >> 16)
                assert total == 0xffff, (path, "invalid IPv4 header checksum")
            frames.append(info)
    return frames


def main():
    report = []
    for name in ("tiny-final", "bigger", "loss", "chat"):
        directory = ROOT / "writeups/check7-data" / name
        run = json.loads((directory / "results.json").read_text(encoding="utf-8"))
        assert run["status"] == "passed" and not run["relay_errors"], name
        assert len(run["transfers"]) == (4 if name == "bigger" else 2), name
        for transfer in run["transfers"]:
            assert transfer["returncode"] == 0 and transfer["match"], (name, transfer)
            assert transfer["received_bytes"] == transfer["expected_bytes"] == 1_048_576
            assert transfer["sha256"] == transfer["expected_sha256"]
        ttl_values = set()
        for link in run["links"]:
            frames = read_capture(directory / link["capture"])
            assert len(frames) == link["frames"], (name, link["name"])
            assert any(frame.get("type") == "ARP" for frame in frames)
            assert any(frame.get("flags", 0) & 2 for frame in frames), "SYN absent"
            assert any(frame.get("flags", 0) & 1 for frame in frames), "FIN absent"
            ttl_values.update(frame["ttl"] for frame in frames if "ttl" in frame)
        assert (125 if name == "bigger" else 127) in ttl_values
        if name == "loss":
            assert sum(link["dropped_data_frames"] for link in run["links"]) == 1
            assert any(link["dropped_data_frames"] and link["repeated_data_ranges"] for link in run["links"])
        if name == "chat":
            assert all(transfer["chat_match"] for transfer in run["transfers"])
            for node in ("C1", "S1"):
                receipts = json.loads((directory / (node + "-downloads/receipts.json")).read_text(encoding="utf-8"))
                assert len(receipts["files"]) == 1 and len(receipts["chats"]) == 1
        report.append({"run": name, "status": "passed", "directions": len(run["transfers"]),
                       "capture_frames": sum(link["frames"] for link in run["links"]),
                       "observed_ttls": sorted(ttl_values)})
    log = (ROOT / "writeups/check7-screenshots/all-ctest.log").read_text(encoding="utf-8")
    assert log.count("Test Passed.") == 40 and "Test Failed." not in log
    log = (ROOT / "writeups/check7-screenshots/chat-protocol-tests.log").read_text(encoding="utf-8")
    assert "Ran 8 tests" in log and "\nOK" in log
    peer_directory = ROOT / "writeups/check7-data/three-host-2026-11-25/attempt-01"
    peer_config = json.loads((peer_directory / "config.json").read_text(encoding="utf-8"))
    assert peer_config.get("three_host_verified"), "Real three-host results still pending"
    peer_result = json.loads((peer_directory / peer_config["verification_file"]).read_text(encoding="utf-8"))
    assert peer_result["status"] == "passed"
    expected_hash = hashlib.sha256(hashlib.shake_256(b"CS144 peer test").digest(1_048_576)).hexdigest()
    received_files = peer_result["received_file_verifications"]
    assert len(received_files) == 2 and len({item["saved_as"] for item in received_files}) == 2
    assert all(item["size"] == 1_048_576 and item["sha256"] == expected_hash for item in received_files)
    for peer, logname in [("A", "probe-A-listener.log"), ("B", "probe-B-listener-02.log")]:
        probe = json.loads((peer_directory / ("probe-" + peer + "-user-reported-passed.json")).read_text(encoding="utf-8"))
        assert probe["status"] == "passed" and len(probe["attempts"]) == 3
        assert all(item["reply"] for item in probe["attempts"])
        assert (peer_directory / logname).read_text(encoding="utf-8-sig").count('"echo":') >= 3
    router_log = (peer_directory / "router-fullstack.stderr.log").read_text(encoding="utf-8")
    assert "src=80.6.5.4 dst=50.9.8.7" in router_log and "src=50.9.8.7 dst=80.6.5.4" in router_log
    assert "runtime error:" not in router_log and "ERROR: AddressSanitizer" not in router_log
    for peer in ["A", "B"]:
        path = peer_directory / ("receipts-" + peer + "-user-reported.json")
        if path.exists():
            receipt = json.loads(path.read_text(encoding="utf-8"))
            assert len(receipt["files"]) == 1
            assert receipt["files"][0]["size"] == 1_048_576 and receipt["files"][0]["sha256"] == expected_hash
    manifest = {}
    for path in sorted((ROOT / "writeups/check7-data").rglob("*")):
        if path.is_file() and path.name != "sha256-manifest.json" and path.suffix != ".pid":
            manifest[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT / "writeups/check7-data/sha256-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "runs": report, "official_tasks": 40,
                      "chat_protocol_tests": 8, "three_host": {"udp_replies": "A 3/3, B 3/3",
                          "received_files": 2, "bytes_each": 1_048_576, "sha256": expected_hash,
                          "provenance": "User-reported endpoint verifications plus local router logs"},
                      "manifest_files": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
