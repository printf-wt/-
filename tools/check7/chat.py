"""A two-person chat and checked file transfer over the project's tcp_eth_udp byte stream."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid


MAX_FILE = 16 * 1024 * 1024
MAX_LINE = 32 * 1024
CHUNK = 12 * 1024


def emit(stream, message):
    data = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(data) > MAX_LINE:
        raise ValueError("message exceeds protocol line limit")
    stream.write(data)
    stream.flush()


def send_file(stream, path):
    path = Path(path)
    # Snapshot the bounded file once: hashing and transmission see identical contents.
    with path.open("rb") as source:
        data = source.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("file exceeds 16 MiB limit")
    transfer = uuid.uuid4().hex
    digest = hashlib.sha256(data).hexdigest()
    emit(stream, {"kind": "file-start", "id": transfer, "name": path.name,
                  "size": len(data), "sha256": digest})
    for offset in range(0, len(data), CHUNK):
        emit(stream, {"kind": "file-chunk", "id": transfer,
                      "data": base64.b64encode(data[offset:offset + CHUNK]).decode("ascii")})
    emit(stream, {"kind": "file-end", "id": transfer})
    return digest


class Receiver:
    def __init__(self, downloads, notify=print):
        self.downloads = Path(downloads)
        self.downloads.mkdir(parents=True, exist_ok=True)
        self.notify = notify
        self.pending = {}
        self.receipts = []
        self.chats = []

    def accept(self, message):
        if not isinstance(message, dict):
            raise ValueError("expected JSON object")
        kind = message.get("kind")
        if kind == "chat":
            name, text = message.get("from"), message.get("text")
            if not isinstance(name, str) or len(name) > 80 or not isinstance(text, str) or len(text) > 2000:
                raise ValueError("invalid chat message")
            self.chats.append({"from": name, "text": text})
            # JSON escaping prevents terminal control sequences from being executed as display controls.
            self.notify("CHAT " + json.dumps({"from": name, "text": text}, ensure_ascii=True))
            return
        transfer = message.get("id", "")
        if not isinstance(transfer, str) or not re.fullmatch(r"[0-9a-f]{32}", transfer):
            raise ValueError("invalid transfer identifier")
        if kind == "file-start":
            name, size, digest = message.get("name"), message.get("size"), message.get("sha256")
            if (not isinstance(name, str) or not name or len(name) > 120 or name in (".", "..")
                    or "/" in name or "\\" in name or any(ord(ch) < 32 for ch in name)):
                raise ValueError("invalid file name")
            if type(size) is not int or not 0 <= size <= MAX_FILE:
                raise ValueError("invalid file size")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid SHA-256")
            if transfer in self.pending or len(self.pending) >= 4:
                raise ValueError("duplicate transfer or too many open files")
            temporary = self.downloads / (transfer + ".part")
            self.pending[transfer] = {"name": name, "size": size, "sha256": digest,
                                      "file": temporary.open("xb"), "temporary": temporary,
                                      "hash": hashlib.sha256(), "received": 0}
            return
        if transfer not in self.pending:
            raise ValueError("transfer has not started")
        state = self.pending[transfer]
        if kind == "file-chunk":
            encoded = message.get("data")
            if not isinstance(encoded, str) or len(encoded) > CHUNK * 4 // 3:
                raise ValueError("invalid chunk size")
            data = base64.b64decode(encoded, validate=True)
            if state["received"] + len(data) > state["size"]:
                raise ValueError("file exceeds declared size")
            state["file"].write(data)
            state["hash"].update(data)
            state["received"] += len(data)
            return
        if kind == "file-end":
            state["file"].close()
            if state["received"] != state["size"] or state["hash"].hexdigest() != state["sha256"]:
                raise ValueError("file length or SHA-256 mismatch")
            destination = self.downloads / (transfer + "-" + state["name"])
            # Hard-link publication fails if the destination already exists; never overwrite a user file.
            os.link(state["temporary"], destination)
            state["temporary"].unlink()
            receipt = {"name": state["name"], "size": state["received"], "sha256": state["sha256"],
                       "saved_as": destination.name}
            self.receipts.append(receipt)
            del self.pending[transfer]
            self.notify("FILE VERIFIED " + json.dumps(receipt, ensure_ascii=True))
            return
        raise ValueError("unknown protocol message")

    def cleanup(self):
        for state in self.pending.values():
            state["file"].close()
            state["temporary"].unlink(missing_ok=True)
        self.pending.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("transport", nargs=argparse.REMAINDER, help="-- path/to/tcp_eth_udp client/server ...")
    args = parser.parse_args()
    command = args.transport[1:] if args.transport[:1] == ["--"] else args.transport
    if not command or not 0 < len(args.name) <= 80:
        parser.error("provide a name of 1-80 characters and a transport command")
    receiver = Receiver(args.downloads, lambda text: print(text, flush=True))
    errors = []
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read_peer():
        try:
            while line := process.stdout.readline(MAX_LINE + 1):
                if len(line) > MAX_LINE or not line.endswith(b"\n"):
                    raise ValueError("oversized or incomplete protocol line")
                receiver.accept(json.loads(line))
            if receiver.pending:
                raise ValueError("peer closed during a file transfer")
        except Exception as error:
            errors.append(str(error))
            process.terminate()
        finally:
            receiver.cleanup()

    thread = threading.Thread(target=read_peer, daemon=True)
    thread.start()
    print("READY: type a message, /send PATH, /quit (EOF also closes your send direction)", flush=True)
    try:
        for line in sys.stdin:
            text = line.rstrip("\r\n")
            if text == "/quit":
                break
            if text.startswith("/send "):
                digest = send_file(process.stdin, text[6:])
                print("FILE SENT sha256=" + digest, flush=True)
            elif text:
                if len(text) > 2000:
                    raise ValueError("chat text exceeds 2000 characters")
                emit(process.stdin, {"kind": "chat", "from": args.name, "text": text})
        process.stdin.close()
        thread.join(timeout=120)
        if thread.is_alive():
            raise TimeoutError("peer did not finish within 120 seconds")
        returncode = process.wait(timeout=15)
        if errors or returncode:
            raise RuntimeError(f"transport={returncode}, protocol={errors}")
        (args.downloads / "receipts.json").write_text(
            json.dumps({"chats": receiver.chats, "files": receiver.receipts}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        thread.join(timeout=3)
        if not thread.is_alive():
            receiver.cleanup()


if __name__ == "__main__":
    main()
