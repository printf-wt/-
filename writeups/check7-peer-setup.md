# Point 7 三机启动与复现说明（2026-11-25 实测）

本说明使用已经完成 UDP 和双向 1 MiB 校验的实际配置。
换网、重启或换机器后先重新核对地址，不能直接套用今天的 IP。
两位同学使用 Ubuntu 虚拟机，用户本人使用 WSL 并运行路由器。

## 1 角色与两层地址

| 角色 | Windows Wi-Fi IPv4 | Ubuntu IPv4 | 宿主机连接 Ubuntu 的地址 |
|---|---|---|---|
| 用户：路由器 | 10.200.49.154 | 172.18.80.5 / WSL | 172.18.80.1 |
| A：客户端 | 10.200.54.254 | 192.168.226.128 / VM | VMnet8：192.168.226.1 |
| B：服务端 | 10.200.93.187 | 192.168.105.128 / VM | VMnet8：192.168.105.1 |

内层虚拟地址仍是 A=80.6.5.4，B=50.9.8.7:80，路由器两侧为 80.0.0.1/50.0.0.1。
它们只存在于实验封装的数据中，不写入 Windows 网卡。
Ubuntu 应先连接宿主机的虚拟网卡地址，再由 Windows 向同学的真实 Wi-Fi 地址转发。

实际采用同一份项目代码在三台电脑部署，参与者以 A/B/用户代称。
不声称是三名同学独立实现的协议栈；没有提供的姓名和 SUNet ID 不虚构。

## 2 准备文件

两位均确认 Ubuntu 24.04.5、GCC 13.3、CMake 3.28.3。
本次克隆失败后改发 [离线包](../output/check7/cs144-point7-offline-20261125.zip)。
里面有源码、已编译 Linux x86_64 端点、聊天工具和 OFFLINE-START.md。

在 Ubuntu 中将包内 cs144-point7-offline-20261125 文件夹提取到 Home，再执行：

```bash
cd "$HOME/cs144-point7-offline-20261125"
chmod +x bin/tcp_eth_udp_sanitized scripts/*.sh tests/*.sh
```

程序需要相应 Ubuntu 运行库；其他系统优先按包内说明从源码构建。
聊天收文件使用同目录硬链接，建议运行于 Ubuntu 本地文件系统。

## 3 Windows 转发脚本

本次使用 [udp-bridge.ps1](../tools/check7/udp-bridge.ps1)。
可下载到 TEMP，也可直接传给同学保存到确定的文件路径。
PowerShell 当前目录若是 C:\Windows\System32，不能假设项目相对路径存在。
下面示例假设脚本在桌面并命名为 udp-bridge.ps1：

```powershell
$bridge = Join-Path ([Environment]::GetFolderPath("Desktop")) "udp-bridge.ps1"
Test-Path $bridge
```

应为 True。若已确认是本项目文件，且 RemoteSigned 因下载标记报未签名，可只解除该文件标记：

```powershell
Unblock-File -LiteralPath $bridge
```

这不改变全局执行策略；若仍受策略阻止，先读取 Get-ExecutionPolicy -List 再处理。
参考：[微软 Unblock-File 文档](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/unblock-file)。

## 4 精确来源的防火墙规则

由各电脑主人在管理员 PowerShell 执行。端口固定，来源只包含对应同学和本机 Ubuntu。
用户路由器两条规则本次是更新已有配置：

```powershell
Set-NetFirewallRule -DisplayName "CS144-Check7-Router50" -RemoteAddress 10.200.93.187,172.18.80.5
Set-NetFirewallRule -DisplayName "CS144-Check7-Router80" -RemoteAddress 10.200.54.254,172.18.80.5
```

新电脑没有旧规则时，需要新建对应 UDP 19050/19080 入站规则。
A 本次新建：

```powershell
New-NetFirewallRule -DisplayName "CS144-Check7-Client-1125" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 12080 -RemoteAddress 10.200.49.154,192.168.226.128
```

B 本次新建：

```powershell
New-NetFirewallRule -DisplayName "CS144-Check7-Server-1125" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 12050 -RemoteAddress 10.200.49.154,192.168.105.128
```

已经创建的规则不必反复新建。若有 Hyper-V 或第三方防火墙限制，按实际诊断处理。
不关闭整机防火墙，也不以 ping 成败替代实际 UDP 往返。

## 5 四个 Windows 转发进程

用户电脑运行两个窗口，脚本路径使用自己的真实绝对路径：

```powershell
& 'D:\计算机网络\课程设计\-\tools\check7\udp-bridge.ps1' -LocalUbuntuIP 172.18.80.5 -LocalPort 9050 -ListenPort 19050 -PeerIP 10.200.93.187 -PeerPort 12050
```

```powershell
& 'D:\计算机网络\课程设计\-\tools\check7\udp-bridge.ps1' -LocalUbuntuIP 172.18.80.5 -LocalPort 9080 -ListenPort 19080 -PeerIP 10.200.54.254 -PeerPort 12080
```

A Windows：

```powershell
& $bridge -LocalUbuntuIP 192.168.226.128 -LocalPort 2080 -ListenPort 12080 -PeerIP 10.200.49.154 -PeerPort 19080
```

B Windows：

```powershell
& $bridge -LocalUbuntuIP 192.168.105.128 -LocalPort 2050 -ListenPort 12050 -PeerIP 10.200.49.154 -PeerPort 19050
```

确认 READY 中每个端口完整，尤其 A 的 PeerPort 是 19080，不是 1908。
READY 只说明本地套接字已绑定，尚不证明对方可达。

## 6 正式连接前先测 UDP

路由器 WSL 可先分别启动 9080、9050 的探测应答端，替代正式程序占用这些端口：

```bash
python3 tools/check7/udp_probe.py listen --port 9080
```

```bash
python3 tools/check7/udp_probe.py listen --port 9050
```

A Ubuntu：

```bash
python3 tools/check7/udp_probe.py send --port 2080 --peer 192.168.226.1 --peer-port 12080
```

B Ubuntu：

```bash
python3 tools/check7/udp_probe.py send --port 2050 --peer 192.168.105.1 --peer-port 12050
```

本次两端均三次回复且 status=passed，本机日志各记录三次回显。
A 初次发往自己 Windows 的 Wi-Fi IP，经 NAT 改写了来源，被严格来源过滤拒绝；
改成 VMnet8 后成功。不要为了这个问题放开任意来源。
通过后退出探测应答进程释放端口，再启动下面的正式路由器。

## 7 正式路由器与端点

用户 WSL，在项目根目录运行并保留日志：

```bash
./build/wsl/apps/fun_router_sanitized \
  interface:stanford:50.0.0.1:9050:172.18.80.1:19050 \
  interface:ucla:80.0.0.1:9080:172.18.80.1:19080 \
  route:50.0.0.0:8:stanford route:80.0.0.0:8:ucla
```

B 先在离线包目录启动服务端：

```bash
python3 tools/check7/chat.py --name B --downloads build/three-host-B -- ./bin/tcp_eth_udp_sanitized server 2050 50.0.0.1 50.9.8.7:80
```

A 再启动客户端：

```bash
python3 tools/check7/chat.py --name A --downloads build/three-host-A -- ./bin/tcp_eth_udp_sanitized client 2080 192.168.226.1:12080 80.0.0.1 80.6.5.4 50.9.8.7:80
```

两边可各输入一句普通文字，确认 CHAT。端点的物理地址、虚拟下一跳、最终目的地址各有用途，不能互换。

## 8 双向 1 MiB 文件校验

两位另开 Ubuntu 终端，在离线包目录生成原文件：

```bash
python3 -c 'import hashlib,pathlib; p=pathlib.Path("build/test-1MiB.bin"); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(hashlib.shake_256(b"CS144 peer test").digest(1048576))'
sha256sum build/test-1MiB.bin
```

原文件预期 SHA-256：

```text
7e7a19f30c8d5d3555721c2923598ef422d464e896fe68906f63f48c91f414fa
```

回到聊天窗口，先 A 发送，B 验证后再由 B 发送：

```text
/send build/test-1MiB.bin
```

接收方须出现 FILE VERIFIED，大小为 1048576，哈希与原文件一致。
不能仅凭 FILE SENT 记为成功。本次两份独立接收记录均已核对通过。

## 9 退出、保存与清理

双方各输入 /quit，等返回命令提示符，应用在下载目录写 receipts.json。
本次提供给助手的是两份 FILE VERIFIED 控制台记录；退出后的正式 JSON 留在参与者机器中。
用户 WSL 路由器和本机两个 Windows 转发由助手在数据核对后停止，两位 Windows 转发可 Ctrl+C。
各电脑主人可在管理员 PowerShell 删除本次不用的入站规则，例如 A：

```powershell
Get-NetFirewallRule -DisplayName "CS144-Check7-Client-1125" | Remove-NetFirewallRule
```

B 对应 Server-1125，用户对应 Router50/Router80。不要删除其他实验规则。
本次实际结果、原始错误与证据目录见 [当日联调记录](check7-session-2026-11-25.md)。
