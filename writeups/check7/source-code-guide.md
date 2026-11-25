# Point 7 新手讲解：让前面的模块组成一张网络

Point 7 以整合与实验为主。前面的 TCP、网络接口和路由器已经写好，
这次让它们在独立程序中实际收发数据，再用自己的 TCP 字节流做聊天和文件校验。
本机实验已通过；2026-11-25 三台电脑的 UDP、双向 TCP 数据与各 1 MiB 接收文件校验也已通过。
两组结果分别保留，三机采用同一份实现部署。

## 1 两层 IP 地址不要混淆

```text
应用文字或文件
  → 自己实现的 TCP 消息
    → 内层 IPv4 数据报（实验虚拟地址）
      → 内层以太网帧（ARP 查询实验下一跳 MAC）
        → Linux UDP（通过真实电脑的地址和端口运送以太网帧）
          → 外层 IP（真实 Wi-Fi、WSL 或虚拟机网络）
```

例如内层客户端仍可叫 `80.6.5.4`，内层服务端叫 `50.9.8.7:80`。
这些地址只在实验程序封装的数据里，不需要写入 Windows 网卡。
外层才使用本次实际的 `10.200.*`、`172.18.*` 和虚拟机内部地址。
换 Wi-Fi 主要改变外层配置，不要求把内层实验网络重新设计一遍。

本机版本用 `127.0.0.1` 代替外层跨机网络。三机版本需要真正让 UDP 穿过各台电脑。
Linux UDP 是传送实验帧的载体，可靠传输仍由我们之前实现的 TCP 完成。

## 2 官方新增的两个应用

| 文件 | 做什么 | 本阶段来源 |
|---|---|---|
| `apps/tcp_eth_udp.cc` | TCP 端点，完成 TCP/IP/Ethernet/UDP 的封装与拆包 | 官方框架 |
| `apps/fun_router.cc` | 读取接口和路由配置，驱动 NetworkInterface 与 Router | 官方框架，附一处编译兼容修正 |
| `apps/CMakeLists.txt` | 注册两个应用及带检查器的版本 | 官方框架 |

`tcp_eth_udp` 的 client 模式主动建立内层 TCP 连接；server 模式监听内层地址。
它通过 `TCPImpSocket` 使用之前的 TCPSender、TCPReceiver 和 ByteStream。
适配器收到 UDP 载荷后解析 Ethernet，把帧交给 NetworkInterface，
再把解析好的 IPv4/TCP 交给 TCPPeer。发送方向按相反顺序封装。

端点的虚拟默认网关用于查询 MAC。物理地址则告诉 UDP 套接字该把一帧发到哪里。
服务端尚未知道外层应答地址时，会从收到的第一份帧学习这个物理来源。

`fun_router` 将 `interface:...` 转成网络接口，将 `route:...` 加入路由表。
事件循环收 UDP、解析帧、调用接口接收，再调用 Point 6 的 `route()`。
它不重新实现最长前缀匹配，也不直接替 TCP 重传数据。

## 3 这次为什么修改三处已有 C++ 代码

| 位置 | 实际问题与修正 |
|---|---|
| `apps/fun_router.cc` | GCC 13 对原范围适配表达式报悬空引用诊断；改为 `args.subspan(1)` 跳过程序名 |
| `util/address.cc` | 默认空地址传入 nullptr 和零长度；UBSan 仍拒绝 memcpy 的空源指针，故零长度时跳过调用 |
| `src/router.hh` | 应用层静态检查要求 Route 字段有显式默认初始化，增加 `{}` |

这三处不改变路由选择或 TCP 收发规则。Point 6 文档中的快照继续保存当时版本。
首次默认空地址失败的原始记录保留在 `check7-data/tiny`，正式通过记录另用新目录。
修复后重新编译带 ASan/UBSan 的应用，完整官方 CTest 40 个任务通过。

## 4 lab.py：怎样自动运行本机实验

`run()` 先构造拓扑，启动真正的 C++ 路由器与端点进程，最后核对结果并清理自己启动的进程。
不是在 Python 里模拟一个假的 TCP 收发器。

| 主要部分 | 作用 |
|---|---|
| `allocate_ports` | 临时分配当前可用的本地 UDP 端口 |
| `link` | 为两个节点建立外层 UDP 隧道代理，登记实际接口参数 |
| `start` | 启动官方应用，分开保存标准错误日志 |
| `exchange` | 双向喂入测试字节、读取接收字节，比较原文及 SHA-256 |
| `finally` 清理 | 停止本次启动的子进程，关闭套接字，保存成功或失败状态 |

单路由拓扑包含两个端点。更大拓扑是 R1-R2-R3 串联，
C1、C2 在左端，S1、S2 在右端，两条 TCP 同时双向传输。
每方向默认 1,048,576 字节，也就是 1 MiB，不是十进制 1,000,000 字节。

测试文件由固定标签的 SHAKE-256 生成，可重复得到相同原文。
实际接收内容必须逐字节相等、哈希相等且进程成功退出，才记为通过。
每次指定的新输出目录必须不存在，防止覆盖旧实验结果。

## 5 Tunnel：为什么能抓帧、丢帧

代理在一个 UDP 端口接收两个已知节点的帧，根据实际来源把它转给另一端。
它不会查看 TCP 确认号来帮忙补发，也不会修改路由器选出的下一跳。

`packet_info` 只解读证据需要的 Ethernet、ARP、IPv4 和 TCP 首部。
`Tunnel.forward` 记录计数和 TTL，再按配置决定是否丢弃第一个带数据的帧。
以后同序号数据范围再次出现，代理可以记录到；真正的重传由 C++ TCP 发送端触发。

抓帧写为标准 Ethernet pcap，每帧只保留前 96 字节，同时记录原始长度。
它足够检查标准 ARP、IP/TCP 首部，不能用来还原完整的传输文件。
文件完整性证据来自应用真正接收到的字节，不从截短的抓帧推算。

一次定点丢帧不等于长期固定百分比丢包实验。
本机正常运行也可能因调度和超时出现重复数据范围，不能声称未注入丢包就没有重传。

## 6 chat.py：应用怎样使用我们自己的 TCP

主程序启动传入的 `tcp_eth_udp` 命令，用子进程标准输入输出承载应用字节。
Python 没有另外用系统 TCP 偷建一条文件传输连接。

本地输入分三种：普通文字发聊天消息，`/send 路径` 发文件，`/quit` 结束本端发送。
对端可继续发送，双方都关闭后，程序保存 `receipts.json`。
一个线程接收对方消息，主线程接受本地输入，因此两个方向可以同时工作。

协议以换行分隔 JSON 对象，TCP 本身只保证字节顺序，不知道“每一句话”的边界。
`emit` 用 JSON 编码后加换行，接收端用有长度上限的 `readline` 取出完整消息。
聊天内容支持 UTF-8；显示时转义控制字符，避免把收到的文字当终端控制命令。

## 7 文件为什么分三种消息

| 消息 | 主要字段 | 意义 |
|---|---|---|
| `file-start` | 唯一 id、文件名、大小、SHA-256 | 声明要接收什么 |
| `file-chunk` | id、Base64 数据 | 逐块运送字节 |
| `file-end` | id | 要求检查完整性并发布文件 |

`send_file` 先读取一份有大小上限的快照，让计算哈希和实际发送看到相同内容。
每块 12 KiB，Base64 使任意二进制字节可以放入 JSON 文本。
Base64 不是加密，也不负责可靠性；可靠性来自 TCP，完整性还要核对哈希。

`Receiver.pending` 按传输 id 保存临时文件、已收字节数、期望大小和增量哈希。
每收到一块，就检查是否超过声明长度，再写临时文件并更新哈希。
收到结束消息后，实际大小和 SHA-256 都相同才接受。

限制包括：单文件最多 16 MiB、最多 4 个在途文件、单消息行长度限制。
文件名不能带路径分隔符或 `..` 目录，临时文件用 `xb` 独占创建。
验证通过后用同目录硬链接发布，目标已存在就失败，不覆盖旧文件。
失败或半途断开时清理自己的未完成临时文件。

**FILE SENT 只表示发送程序已写出协议字节，不证明对方接收成功。**
验收要看接收端 FILE VERIFIED、实际保存文件和收据，再对照发送原文哈希。

## 8 Windows 转发与 UDP 预检

`udp-bridge.ps1` 在两个预先指定的 IP:端口之间原样转发 UDP。
一端是本机 Ubuntu，另一端是同学 Windows；不符合这两个端点的来源被忽略。
NAT/虚拟机内部地址不直接暴露给远处电脑，Windows 接收到外层包后转给本机 Ubuntu。

本机有两侧路由接口，因此有两个 Windows 转发进程。
每位同学一个端点，对应一个转发进程；IP 和端口必须与启动参数一致。
脚本显示 READY 只说明端口已经绑定，不证明另一台电脑收到数据。

`udp_probe.py` 是 11 月 25 日增加的预检，不运行 TCP。
listen 回显带实验标记的小消息；send 发送随机标识的探测并要求匹配应答。
三次都成功才通过，否则非零退出；Windows 收到无监听端点的 ICMP 复位也会明确记失败。
这能先检查外层通路，避免直接等待复杂 TCP 连接再猜哪里断了。
预检结束要关闭监听程序，释放端口，再启动正式 C++ 应用。

## 9 怎么阅读真实记录

- `check7-data/tiny-final`：一台路由器的双向 1 MiB，通过。
- `check7-data/bigger`：三台路由器、两条并发 TCP、四个方向各 1 MiB，通过。
- `check7-data/loss`：定点丢一帧后的双向文件恢复，通过。
- `check7-data/chat`：聊天和校验文件的本机全栈实验，通过。
- `check7-data/three-host-2026-11-25`：真实三机 UDP 往返、双向数据及两份 1 MiB 接收验证，通过。

`results.json` 保存命令、端口、路由、退出码及收发哈希。
`stderr.log` 是官方程序实际输出，不能把调试文字混进二进制文件的数据流。
聊天收据记录文件大小、哈希和最终文件名；正式副本不重复提交生成的原始大文件。

`validate.py` 核对保存记录中的 pcap 格式、首部校验和、计数、SYN/FIN、TTL 和哈希，
再核对真实三机回传与路由器日志，输出原始证据的 SHA-256 清单。它检查记录一致性，不能替代重新跨机传输。
`build_report.py` 从指定已通过的 JSON 生成 Markdown/PDF；未验证的三机结果必须保留待验证状态。

## 10 从头复现与本次三机命令

本机构建和实验见 [工具说明](../../tools/check7/README.md)。
实际三机配置见 [启动与复现说明](peer-setup.md)。
新网络状态见 [11 月 25 日联调记录](sessions/2026-11-25.md)。
本次三机步骤已经验证；换网后应重新核对实际地址，不套用旧命令。

## 11 完整自编工具快照

下列快照用于对照学习，取自本次工作区的实际文件。
官方新增应用可直接阅读 apps/tcp_eth_udp.cc 和 apps/fun_router.cc。
这些代码、实验工具与说明由 Codex 按用户要求辅助完成。

<details>
<summary>tools/check7/chat.py 完整源码</summary>

```python
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
```

</details>

<details>
<summary>tools/check7/lab.py 完整源码</summary>

```python
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
```

</details>

<details>
<summary>tools/check7/udp_probe.py 完整源码</summary>

```python
"""Check the physical UDP path before starting the TCP/IP endpoints. No TCP is implemented here."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import socket
import time


MAGIC = b"CS144-POINT7-PROBE-v1 "


def listen(args):
    deadline = time.monotonic() + args.duration
    received = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        sock.settimeout(0.5)
        print(f"READY probe UDP {args.bind}:{args.port}; Ctrl+C to stop", flush=True)
        while time.monotonic() < deadline:
            try:
                payload, source = sock.recvfrom(1024)
            except (socket.timeout, ConnectionResetError):
                continue
            if len(payload) > 256 or not payload.startswith(MAGIC):
                continue
            sock.sendto(payload, source)
            received += 1
            print(json.dumps({"echo": received, "source": list(source), "bytes": len(payload)}), flush=True)
    return {"mode": "listen", "echoed": received, "status": "finished"}


def send(args):
    nonce = secrets.token_hex(16).encode("ascii")
    target = (args.peer, args.peer_port)
    results = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        for index in range(args.count):
            payload = MAGIC + nonce + b" " + str(index).encode("ascii")
            started = time.monotonic()
            deadline = started + args.timeout
            sock.sendto(payload, target)
            result = {"attempt": index + 1, "reply": False}
            while time.monotonic() < deadline:
                sock.settimeout(max(0.001, deadline - time.monotonic()))
                try:
                    received, source = sock.recvfrom(1024)
                except socket.timeout:
                    break
                except ConnectionResetError as error:
                    result["error"] = str(error)
                    break
                if received == payload:
                    result.update(reply=True, rtt_ms=(time.monotonic() - started) * 1000,
                                  source=list(source))
                    break
            results.append(result)
            print(json.dumps(result), flush=True)
    return {"mode": "send", "status": "passed" if all(item["reply"] for item in results) else "failed",
            "local_port": args.port, "target": list(target), "attempts": results,
            "scope": "UDP connectivity only; not TCP, chat or file verification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["listen", "send"])
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True, help="local UDP port of the eventual endpoint/router")
    parser.add_argument("--peer", help="physical IPv4 address of the bridge or direct peer")
    parser.add_argument("--peer-port", type=int)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=2)
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.count < 1 or args.timeout <= 0 or args.duration <= 0:
        parser.error("invalid port/count/time limit")
    if args.mode == "send":
        if args.peer is None or args.peer_port is None or not 1 <= args.peer_port <= 65535:
            parser.error("send requires --peer and --peer-port")
        try:
            socket.inet_pton(socket.AF_INET, args.peer)
        except OSError:
            parser.error("--peer must be a numeric IPv4 address")
    if args.output and args.output.exists():
        parser.error("output file already exists; use a new filename")
    result = listen(args) if args.mode == "listen" else send(args)
    result["recorded_utc"] = datetime.now(timezone.utc).isoformat()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result), flush=True)
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

</details>

<details>
<summary>tools/check7/udp-bridge.ps1 完整源码</summary>

```powershell
param(
    [Parameter(Mandatory=$true)][string]$LocalUbuntuIP,
    [Parameter(Mandatory=$true)][int]$LocalPort,
    [Parameter(Mandatory=$true)][int]$ListenPort,
    [Parameter(Mandatory=$true)][string]$PeerIP,
    [Parameter(Mandatory=$true)][int]$PeerPort
)

$ErrorActionPreference = 'Stop'
$localAddress = [System.Net.IPAddress]::Parse($LocalUbuntuIP)
$peerAddress = [System.Net.IPAddress]::Parse($PeerIP)
if ($localAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    $peerAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
    throw 'IPv4 addresses are required.'
}
foreach ($number in @($LocalPort, $ListenPort, $PeerPort)) {
    if ($number -lt 1 -or $number -gt 65535) { throw 'Ports must be in 1..65535.' }
}
if ($LocalUbuntuIP -eq $PeerIP -and $LocalPort -eq $PeerPort) {
    throw 'The two endpoints must be different.'
}

$udp = [System.Net.Sockets.UdpClient]::new($ListenPort)
$udp.Client.ReceiveTimeout = 1000
$localTarget = [System.Net.IPEndPoint]::new($localAddress, $LocalPort)
$peerTarget = [System.Net.IPEndPoint]::new($peerAddress, $PeerPort)
$sentLocal = 0
$sentPeer = 0
Write-Output "READY UDP :$ListenPort Ubuntu=$localTarget peer=$peerTarget (Ctrl+C to stop)"
try {
    while ($true) {
        $source = [System.Net.IPEndPoint]::new([System.Net.IPAddress]::Any, 0)
        try { $payload = $udp.Receive([ref]$source) }
        catch [System.Net.Sockets.SocketException] {
            if ($_.Exception.SocketErrorCode -eq [System.Net.Sockets.SocketError]::TimedOut) { continue }
            throw
        }
        if ($source.Address.Equals($localAddress) -and $source.Port -eq $LocalPort) {
            [void]$udp.Send($payload, $payload.Length, $peerTarget)
            $sentPeer++
        } elseif ($source.Address.Equals($peerAddress) -and $source.Port -eq $PeerPort) {
            [void]$udp.Send($payload, $payload.Length, $localTarget)
            $sentLocal++
        } else {
            Write-Output "IGNORED unexpected sender $source"
            continue
        }
        if (($sentPeer + $sentLocal) -le 4 -or ($sentPeer + $sentLocal) % 500 -eq 0) {
            Write-Output "FORWARDED to-peer=$sentPeer to-Ubuntu=$sentLocal"
        }
    }
} finally {
    $udp.Dispose()
    Write-Output "STOPPED to-peer=$sentPeer to-Ubuntu=$sentLocal"
}
```

</details>
