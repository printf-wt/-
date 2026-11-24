# Checkpoint 4：让同学主机能够被测量

先确认两台电脑的网络位置，再判断怎样连接。本说明用于双方同意的 ICMP 测量，
同学不需要把项目源码、GitHub 密码或电脑账户交给你。

## 1 同一 Wi-Fi 或路由器

如果同学使用 Windows，让他按 Win+R，输入 cmd，回车后执行：

```bat
ipconfig
```

找到正在使用的 WLAN/无线局域网适配器或以太网适配器，读取其中的 IPv4 地址。
不使用“媒体已断开”的适配器，也不把 WSL、虚拟机的内部地址当成 Wi-Fi 地址。
例如，192.168.1.20 是一个示例地址，应换成同学电脑实际显示的值。

收到地址后，你在 Windows PowerShell 中先测试：

```powershell
ping -n 4 192.168.1.20
```

这里每行出现“来自……的回复”说明 Windows 路径可达。
随后还要在实际采集所在的 Ubuntu 中测试一次：

```bash
ping -n -c 4 -W 2 192.168.1.20
```

只有实际采集环境能够收到回复，才开始一小时测量。
同一个校园 Wi-Fi 名称并不能保证主机互通；校园网可能有客户端隔离或不同子网。

## 2 Windows 防火墙拦截时

先确认 IP 无误、同学电脑在线，再考虑这一步。
让同学以管理员身份打开 PowerShell，添加只允许你这台电脑发来的 Echo Request 的规则。
下面 192.168.1.10 是“你的电脑”的示例地址，需要替换成你在当前网络中的实际 IPv4：

```powershell
New-NetFirewallRule -Name "CS144-Check4-Ping" -DisplayName "CS144 Checkpoint 4 Ping" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -RemoteAddress 192.168.1.10 -Profile Any -Action Allow
```

这条规则只允许指定来源的 ICMPv4 Echo Request，不需要关闭整个防火墙。
如果规则名称已经存在，先检查已有规则，不要反复新建不同名称的规则。
若 WSL 或 VPN 改变了实际源地址，应先核实源地址，再调整范围。

实验结束后，同学可在管理员 PowerShell 中删除本次规则：

```powershell
Remove-NetFirewallRule -Name "CS144-Check4-Ping"
```

Windows 的网络属性界面也可查看 IPv4 地址：
设置 → 网络和 Internet → 当前连接 → 属性。

## 3 不同 Wi-Fi 或不同地点

192.168.*、10.*、172.16.* 到 172.31.* 是私网地址，通常不能跨互联网直接访问。
直接交换这类地址或路由器的公网地址，并不会自动让两台电脑互通。

可以使用双方已经配置好的校园 VPN/实验私网，交换 VPN 中可达的主机地址；
也可以约好接入同一个允许设备互访的路由器或热点，再按前面的流程检查。
如果要新建跨网 VPN，先说明双方系统和现有网络，再选择配置方式。
没有确认路径可达前，不修改路由器端口转发或关闭防火墙。

普通 ping 只需要目标主机响应 ICMP，无须同学运行服务器或开放 TCP 端口。
保持同学电脑联网、不休眠约一小时即可；采集和分析由你这台电脑完成。
当前项目使用的是实际可达的同学路径，不能把它描述为课程专用 CS144 私网。

参考：[微软 IP 地址查看方法](https://support.microsoft.com/en-us/windows/experience/connectivity-networking/essential-network-settings-and-tasks-in-windows)、
[微软防火墙规则参数](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule)。

## 4 本次实际配置记录

2026 年 11 月 24 日，你的 Wi-Fi 地址为 10.200.45.250，同学为 10.200.31.238，
本机 WLAN 前缀为 /15，路由检查显示目标位于本地子网。
最初 Windows 和 WSL 都没有收到 Echo Reply。
同学添加限定来源为 10.200.45.250 的上述规则后，两种环境均收到 3/3 个回复；
WSL 试测 RTT 为 13.1、14.0、21.0 ms。
Windows tracert 随后的输出只显示一个目标跳点。

正式采集随后开始，每 0.2 秒一次，单次计划时长 3602 秒。
这份记录描述本次操作顺序；同学的防火墙由同学本人修改，未通过远程控制操作。
更换 Wi-Fi 或地址后，应重新核实来源和目标，不能照抄本次地址继续放行。

## 5 更换局域网后的重试

随后双方更换网络，本机变为 172.20.10.3/28，同学变为 172.20.10.2。
旧采集提前结束且不足一小时，其原始记录已清理，未与新数据拼接。
同学在管理员 PowerShell 中更新原规则：

```powershell
Set-NetFirewallRule -Name "CS144-Check4-Ping" -RemoteAddress 172.20.10.3
```

更新后 Windows 与 WSL 均收到 3/3 回复，WSL RTT 为 7.92、25.5、24.0 ms。
新测量单独写入 check4-data/network2，并重新开始完整的一小时采集。
实验结束后仍可使用前文的 Remove-NetFirewallRule 清理同一条临时规则。
