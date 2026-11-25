# Point 7 三台电脑启动说明

> 本文中的具体地址属于 **2026-11-24 的旧配置**。
> 2026-11-25 已更换 Wi-Fi 和同学机器，暂勿复制下方旧 IP 命令执行。
> 新一轮实际状态见 [11 月 25 日联调记录](check7-session-2026-11-25.md)，收齐新地址后再更新启动命令。

本说明使用用户提供的实际地址。三台 Windows 应连接同一个局域网。
这些配置已准备好，跨电脑通信是否成功需要三个人实际启动后再确认。
当前本机回环实验不能代替三机实验结果。

## 1 分工与地址

| 角色 | Windows 局域网 IPv4 | Ubuntu 内部 IPv4 | 系统 |
|---|---|---|---|
| 你：路由器 | 172.20.10.3 | 172.18.80.5 | WSL |
| 同学 A：客户端 | 172.20.10.2 | 172.18.199.141 | WSL |
| 同学 B：服务端 | 172.20.10.7 | 192.168.217.128 | 虚拟机 |

以上地址会因重启或换网络而改变；开始前在 Windows `ipconfig`、Ubuntu `hostname -I`
核对。`169.254.144.1` 是另一条实验接口，未作为这次跨机隧道地址。

本次虚拟网络仍用：客户端 80.6.5.4，服务端 50.9.8.7:80，
路由器两侧接口 80.0.0.1 和 50.0.0.1。这些地址不需要写进 Windows 网卡设置。

## 2 为什么增加 Windows UDP 转发

WSL 和虚拟机内部地址未必能从另一台电脑直接访问。
本方案在每台 Windows 上运行一个固定两端的 UDP 转发脚本，
将外层 UDP 在已配置的本机 Ubuntu 与同学 Windows 之间转发。
脚本不实现 TCP、ARP 或选路；协议行为仍由 Ubuntu 中的项目源码完成。
它只接受指定 IP 和源端口的两个端点，不转发其他来源。

不要使用只支持 TCP 的 `netsh interface portproxy` 代替这里的 UDP 转发。
这里不要求切换 WSL 网络模式，也不要求修改虚拟机桥接模式。
微软背景说明：[WSL 网络](https://learn.microsoft.com/en-us/windows/wsl/networking)。

## 3 准备项目与编译

两位同学可在 Ubuntu 中新建独立副本，不覆盖自己原来的实验目录：

```bash
git clone https://github.com/printf-wt/C-NET_class-design.git cs144-point7
cd cs144-point7
```

若仓库访问需要登录，使用自己的已获授权账号，或由仓库主人提供代码副本。
已经取得这个副本的同学先 `git pull --ff-only`。然后在各自仓库根目录执行：

```bash
g++ --version
cmake --version
python3 --version
cmake -S . -B build/wsl -DSANITIZED_APPS=True
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target tcp_eth_udp_sanitized fun_router_sanitized
```

本项目验证环境为 Ubuntu 24.04、GCC 13、CMake 3.28；框架要求 C++23 和 CMake≥3.24。
如果同学版本较旧且编译失败，先保留错误输出，不必反复运行。
本地源码已做 GCC 13 范围遍历兼容修正与默认空地址的 UBSan 修正。
不要从官方 startercode 单独下载未实现的 TCP 模块来替换自己的源码。

## 4 Windows 侧准备

Windows 中打开 PowerShell，进入项目目录。WSL 可通过文件资源管理器的 Linux 项
找到 Ubuntu 中的仓库，也可将仓库中的 `tools/check7/udp-bridge.ps1` 复制到 Windows。
复制脚本时保留其真实文件内容，下面命令的路径按实际位置填写。

你这台电脑的每个 PowerShell 窗口先执行：

```powershell
Set-Location -LiteralPath 'D:\计算机网络\课程设计\-'
Test-Path .\tools\check7\udp-bridge.ps1
```

应返回 True。管理员 PowerShell 默认常在 C:\Windows\System32，
不能从那里直接使用项目相对路径。两位同学请切到他们自己的项目位置，
或者复制脚本的完整路径后，用 `& '脚本完整路径'` 加对应参数启动。

每台电脑需允许本次指定 UDP 端口。以下命令由该电脑主人在**管理员 PowerShell**运行，
只开放列出的来源，不关闭整个防火墙。

你这台路由器 Windows：

```powershell
New-NetFirewallRule -DisplayName "CS144-Check7-Router50" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 19050 -RemoteAddress 172.20.10.7,172.18.80.5
New-NetFirewallRule -DisplayName "CS144-Check7-Router80" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 19080 -RemoteAddress 172.20.10.2,172.18.80.5
```

同学 A 的 Windows：

```powershell
New-NetFirewallRule -DisplayName "CS144-Check7-Client" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 12080 -RemoteAddress 172.20.10.3,172.18.199.141
```

同学 B 的 Windows：

```powershell
New-NetFirewallRule -DisplayName "CS144-Check7-Server" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 12050 -RemoteAddress 172.20.10.3,192.168.217.128
```

若额外的 Hyper-V、第三方防火墙或虚拟机软件阻断流量，仍需针对实际错误处理；
普通 Windows 入站规则不是跨机联通成功的证明。

## 5 开四个 Windows 转发窗口

你这台开两个 PowerShell，分别保持以下命令运行：

```powershell
& .\tools\check7\udp-bridge.ps1 -LocalUbuntuIP 172.18.80.5 -LocalPort 9050 -ListenPort 19050 -PeerIP 172.20.10.7 -PeerPort 12050
```

```powershell
& .\tools\check7\udp-bridge.ps1 -LocalUbuntuIP 172.18.80.5 -LocalPort 9080 -ListenPort 19080 -PeerIP 172.20.10.2 -PeerPort 12080
```

同学 A 的 Windows：

```powershell
& .\tools\check7\udp-bridge.ps1 -LocalUbuntuIP 172.18.199.141 -LocalPort 2080 -ListenPort 12080 -PeerIP 172.20.10.3 -PeerPort 19080
```

同学 B 的 Windows：

```powershell
& .\tools\check7\udp-bridge.ps1 -LocalUbuntuIP 192.168.217.128 -LocalPort 2050 -ListenPort 12050 -PeerIP 172.20.10.3 -PeerPort 19050
```

应显示 READY，之后实际转发时显示 FORWARDED 计数。
如果 PowerShell 提示执行策略阻止脚本或端口占用，保留报错再处理；不用重装 Ubuntu。

## 6 启动三个 Ubuntu 角色

先在你的 Ubuntu 仓库目录运行路由器，窗口保持开启：

```bash
./build/wsl/apps/fun_router_sanitized \
  interface:stanford:50.0.0.1:9050:172.20.10.3:19050 \
  interface:ucla:80.0.0.1:9080:172.20.10.3:19080 \
  route:50.0.0.0:8:stanford route:80.0.0.0:8:ucla
```

然后同学 B 在自己的 Ubuntu 启动聊天室服务端：

```bash
python3 tools/check7/chat.py --name classmate-B --downloads build/check7-peer-B -- \
  ./build/wsl/apps/tcp_eth_udp_sanitized server 2050 50.0.0.1 50.9.8.7:80
```

最后同学 A 在自己的 Ubuntu 启动客户端：

```bash
python3 tools/check7/chat.py --name classmate-A --downloads build/check7-peer-A -- \
  ./build/wsl/apps/tcp_eth_udp_sanitized client 2080 172.20.10.2:12080 80.0.0.1 80.6.5.4 50.9.8.7:80
```

注意，客户端连接的物理地址是**自己 Windows 的转发端口**，
转发脚本再送给你的路由器 Windows。虚拟下一跳仍为 80.0.0.1。
服务端从第一份帧学习本地转发端的物理应答地址。

## 7 聊天与 1 MiB 文件校验

连接成功后 A、B 各输入一句话，确认对方出现 CHAT 提示。
双方各在另一个 Ubuntu 终端生成测试文件：

```bash
python3 -c 'import hashlib,pathlib; pathlib.Path("build/check7-test.bin").write_bytes(hashlib.shake_256(b"CS144 peer test").digest(1048576))'
sha256sum build/check7-test.bin
```

回到聊天窗口输入：

```text
/send build/check7-test.bin
```

发送端出现 FILE SENT，接收端应出现 FILE VERIFIED，包含字节数和 SHA-256。
分别记录两个方向的结果。也可对接收端保存的文件再运行 `sha256sum`。
聊天结束时双方输入 `/quit`，等待双方关闭及 receipts.json 写入。
应用需要两边都结束发送；只一方退出时，另一方仍可以发消息。

交回实际参与者姓名或你们选择的代称、Ubuntu 类型、发送和接收哈希、
两侧聊天日志及任何报错，才能把报告中的“三机待验证”改成实际结果。
没有 Stanford SUNet ID 就说明非 Stanford 环境，不虚构学号。

## 8 实验结束

各 Windows 转发窗口 Ctrl+C，路由器 Ubuntu 窗口 Ctrl+C。
各电脑主人在管理员 PowerShell 清理本次规则：

```powershell
Get-NetFirewallRule -DisplayName "CS144-Check7-*" | Remove-NetFirewallRule
```

先前 Checkpoint 4 的 ping 规则不是这些名称，不受这条清理命令影响。
整个联通阶段建议预留 20-30 分钟，首次编译和排查另计；没有强制一小时要求。
