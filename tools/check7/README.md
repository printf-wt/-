# Point 7 全栈实验工具

先看[三机说明](../../writeups/check7-peer-setup.md)区分本机验证和跨电脑联调。
本目录没有创建虚假的 check7 CMake 目标，实际使用官方应用和完整 CTest。

## 构建（Ubuntu）

```bash
cmake -S . -B build/wsl -DSANITIZED_APPS=True
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target tcp_eth_udp_sanitized fun_router_sanitized
```

## 本机复现

以下输出目录必须不存在，脚本不会覆盖前一次运行。

```bash
python3 tools/check7/lab.py --sanitized --output build/my-check7/tiny
python3 tools/check7/lab.py --sanitized --topology bigger --output build/my-check7/bigger
python3 tools/check7/lab.py --sanitized --drop-first-data --output build/my-check7/loss
python3 tools/check7/lab.py --sanitized --chat --output build/my-check7/chat
```

每次默认每方向传 1,048,576 字节，等待约 30 秒，含 TCP 关闭等待。
需要改变大小时用 --size；需要保留原始接收文件用 --save-payloads。
聊天室运行会保留实际发出/收到的文件，但仓库中的证据副本不包含这些重复二进制数据。
results.json 保存实际进程命令、动态端口、路由表、逐字节/哈希校验和退出状态。
pcap 是 UDP 代理处记录的内层 Ethernet，每帧最多保存 96 字节，原始长度保留。
首部抓帧不能还原文件；文件哈希来自实际应用接收的数据。

## 验证与报告

```bash
CMAKE_BUILD_PARALLEL_LEVEL=4 ctest --test-dir build/wsl --output-on-failure
python3 tools/check7/test_chat.py
python3 tools/check7/validate.py
```

validate.py 对仓库内指定正式记录核对 pcap 首部、计数、SYN/FIN、TTL、哈希和测试日志，
并核对真实三机的两份接收校验与本机路由器记录，
并重新生成原始记录的 SHA-256 清单。初次失败的 tiny 目录单独保留，不计为成功。

PDF 生成器依赖 reportlab 和中文 TrueType 字体，可在已有依赖的 Windows Python 运行：

```powershell
python -X utf8 tools/check7/build_report.py
```

其他平台用 --font 指定中文 .ttf，--pdf 与 --markdown 可指定输出位置。
生成后需渲染并目检，避免字体缺字、溢出或表格截断。

## 聊天应用

chat.py 包装官方 tcp_eth_udp，协议是一行一个 JSON 对象，不另外建立系统 TCP 数据连接。
支持普通消息、`/send 路径`、`/quit`；收据在所选 downloads 目录。
完整三机命令见说明文档，单独传输时也可直接使用官方 tcp_eth_udp。
文件采用分块 Base64、长度及 SHA-256 校验。单文件上限 16 MiB，最多 4 个在途文件。
拒绝路径穿越，临时文件独占创建，验证后原子发布且不覆盖已有文件。
此处原子发布使用同一目录文件的硬链接，适用于本实验的 Linux 文件系统。

## Windows UDP 转发

udp-bridge.ps1 仅在固定两端之间转发 UDP，需要各电脑主人按说明配置入站端口。
在 Windows Python 中运行 `python tools/check7/verify_bridge.py` 可复现 4 项回环检查。
脚本不改变 Windows 路由表、WSL 模式或全局防火墙状态。
这个回环检查不是同学电脑可达性的证明。

## 三机启动前的 UDP 预检

换网络或换机器后先收集新地址。udp_probe.py 可复用正式实验的 UDP 端口验证物理链路。
在对端运行 listen，在本机运行 send，具体 IP 和端口按新拓扑填写：

```text
python3 tools/check7/udp_probe.py listen --port 对端本地UDP端口
python3 tools/check7/udp_probe.py send --port 本机本地UDP端口 --peer 下一段物理IPv4 --peer-port 下一段UDP端口
```

以上是参数说明，中文部分不是可直接执行的配置。使用转发时，下一段物理地址可以是本机 Windows 转发端。
listen 最长默认运行 300 秒；Ctrl+C 可提前停止。预检结束后先退出，释放端口再启动正式程序。
send 默认发送三次带随机标识的小探测，全部收到匹配应答才通过；支持 --output 新JSON文件保存结果。
探测不能证明 TCP、聊天室或文件传输通过，这些仍需分别验收。
