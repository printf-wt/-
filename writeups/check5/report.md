# Checkpoint 5：网络接口与 ARP

本阶段完成 NetworkInterface，将 IPv4 数据报封装成以太网帧，
并通过 ARP 查询下一跳的 MAC 地址。接收方向解析以太网载荷。
框架来自官方 check5-startercode，提交 3411cca9fe3ae099be46544d6379158a733b0582。
要求依据：[官方 Checkpoint 5 指导书](https://cs144.github.io/assignments/check5.pdf)。

## 结构与设计

- mappings_ 按下一跳 IPv4 保存 MAC 和剩余期限，收到有效 ARP 后保留 30 秒。
- pending_ 按下一跳保存 FIFO 数据报队列及 5 秒等待期限。
- 已知 MAC 时直接发 IPv4；未知时先入队，再广播一次 ARP 请求。
- 同一等待期不重复请求；5 秒届满清理该请求及其全部待发数据报。
- 有效 ARP 请求和应答均刷新发送者映射，并释放对应待发队列。
- 只有询问本机 IP 的 ARP 请求才得到应答。
- tick 使用剩余时间，先比较再相减，避免累计时钟加法溢出。
- std::map 查找为 O(log n)，每次 tick 遍历现有表项。

## 实现中的关键问题

ARP 查询 next_hop，而不是 IP 数据报最终目的地址；封装不改目的 IP。
先过滤目的 MAC，再根据 EtherType 处理 IPv4、ARP 或忽略未知类型。
解析失败的数据不进入接收队列，也不更新 ARP 缓存。
发送前先建立等待队列；收到映射后先移出并删除队列，再调用输出端口，
使同步回调不会继续使用已失效的容器迭代器。

## 实际验证

官方 check5 的 3 个 CTest 任务通过，包含多场景 net_interface 测试。
另跑 check3 回归 37/37、check0 回归 11/11，补充 ASan/UBSan 场景 5/5。
补充检查覆盖精确过期边界、缓存刷新、极大 tick、非法帧和同步双接口通信。
clang-tidy 与本阶段两份源码的 clang-format 检查通过。
[验证摘要及原始记录](logs/validation.txt)。

## 学习材料与截图

[逐函数新手讲解与完整源码](source-code-guide.md)。
实际桌面截图：[发送](screenshots/01-send-datagram.jpg)、
[接收 ARP](screenshots/02-receive-arp.jpg)、
[封装](screenshots/03-expiry-and-encapsulation.jpg)、
[完整超时处理](screenshots/04-expiry.jpg)。

## 剩余问题与协助说明

上述测试中未发现剩余错误；本阶段使用内存模拟端口，未做真实 TAP 实网验证。
等待期内的队列没有额外容量上限；未增加自动重试或 ICMP 不可达消息。
这些未增加的功能不属于本次接口要求。
按用户“开始做 point5、截图、讲清源码和修改后 push”的请求，
代码、验证与文档由 Codex 辅助完成；未填写未经提供的姓名、SUNet ID 或耗时。
