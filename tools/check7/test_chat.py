"""Protocol and file publication checks, independent of the C++ transport."""

import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from chat import MAX_FILE, Receiver, send_file


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.receiver = Receiver(self.root / "received", lambda _: None)
        self.transfer = "a" * 32

    def tearDown(self):
        self.receiver.cleanup()
        self.temporary.cleanup()

    def start(self, data=b"abc", **overrides):
        message = {"kind": "file-start", "id": self.transfer, "name": "sample.bin",
                   "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        self.receiver.accept({**message, **overrides})

    def chunk(self, data=b"abc"):
        self.receiver.accept({"kind": "file-chunk", "id": self.transfer,
                              "data": base64.b64encode(data).decode()})

    def finish(self):
        self.receiver.accept({"kind": "file-end", "id": self.transfer})

    def test_binary_roundtrip(self):
        data = hashlib.shake_256(b"binary fixture").digest(200_123)
        source = self.root / "binary.bin"
        source.write_bytes(data)
        wire = io.BytesIO()
        digest = send_file(wire, source)
        for line in wire.getvalue().splitlines():
            self.receiver.accept(json.loads(line))
        receipt = self.receiver.receipts[0]
        self.assertEqual((self.receiver.downloads / receipt["saved_as"]).read_bytes(), data)
        self.assertEqual(digest, receipt["sha256"])

    def test_empty_file(self):
        self.start(b"")
        self.finish()
        self.assertEqual(self.receiver.receipts[0]["size"], 0)

    def test_unicode_chat(self):
        self.receiver.accept({"kind": "chat", "from": "同学甲", "text": "网络实验，你好！"})
        self.assertEqual(self.receiver.chats[0]["text"], "网络实验，你好！")

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.start(name="../outside.bin")
        self.assertEqual(list(self.receiver.downloads.iterdir()), [])

    def test_size_limit_rejected(self):
        with self.assertRaises(ValueError):
            self.start(size=MAX_FILE + 1)

    def test_corruption_not_published(self):
        self.start()
        self.chunk(b"abd")
        with self.assertRaises(ValueError):
            self.finish()
        self.receiver.cleanup()
        self.assertEqual(list(self.receiver.downloads.iterdir()), [])

    def test_declared_size_enforced(self):
        self.start(size=2)
        with self.assertRaises(ValueError):
            self.chunk()

    def test_existing_destination_not_overwritten(self):
        self.start()
        self.chunk()
        destination = self.receiver.downloads / (self.transfer + "-sample.bin")
        destination.write_bytes(b"keep original")
        with self.assertRaises(FileExistsError):
            self.finish()
        self.assertEqual(destination.read_bytes(), b"keep original")


if __name__ == "__main__":
    unittest.main(verbosity=2)
