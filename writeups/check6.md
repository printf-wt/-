# Checkpoint 6：IPv4 路由器

本阶段在 Point 5 的 NetworkInterface 上实现 Router。
框架：官方 check6-startercode，提交 87b5778a009a63f86f35c7b79ae9fee735e4fb98。
要求：[官方指导书](https://cs144.github.io/assignments/check6.pdf)。

## 结构与设计

- router.hh 增加 Route 结构及 routes_ 向量，公共接口保持原样。
- 每条记录保存规范化前缀、掩码、前缀长度、可选下一跳和出口编号。
- add_route 预计算掩码，清除前缀中的主机位，追加一条记录。
- route 遍历所有接口的接收队列，对每个数据报线性扫描路由表。
- 匹配目的地址高位，选择前缀长度最长的一条；无匹配则丢弃。
- 同长度匹配保留先加入的记录，不实现多路径分流。
- 显式下一跳交给对应网关；空 optional 表示直接交给目的主机。
- 转发前 TTL 减一并重算 IPv4 首部校验和，最终目的 IP 和载荷保持。
- ARP 与以太网封装复用 Point 5；路由器只处理 IP 数据报。
- R 条路由、D 个待处理数据报、I 个接口的处理为 O(I+D×R)。

## 实现中的关键问题

/0 单独生成零掩码，避免将 32 位整数移位 32 位；/32 可以精确匹配。
拒绝超过 32 的前缀长度，再做移位；调用者仍需提供有效接口编号。
TTL 在递减前检查，0 或 1 直接丢弃，避免无符号下溢。
先从接收队列移出并删除数据报，再选路，丢弃分支也会继续处理后续数据。
最长匹配不依赖路由按长度排序；加入时掩码化可接受带主机位的前缀。
修改 TTL 后调用框架 compute_checksum，序列化本身不会自动重算校验和。

## 实际验证

官方 check6：4/4 CTest 任务通过，包含网络接口和模拟网络中的路由测试。
check3 回归 37/37，check0 回归 11/11；补充 ASan/UBSan 场景 5/5。
补充覆盖 33 种前缀长度、128 条路由与 512 个目的地址的独立算术对照，
以及 TTL、空表、队列排空、直连/网关 ARP 和非法 /33。
clang-tidy 及两份新源文件的 clang-format 检查均通过，官方测试未修改。
[验证摘要](check6-screenshots/validation.txt)。

## 学习资料与截图

[逐函数讲解、手算与完整源码](check6-source-code-guide.md)。
[添加路由截图](check6-screenshots/01-add-route.jpg)；
[最长匹配与转发截图](check6-screenshots/02-route-forwarding.jpg)。

## 剩余问题与协助说明

上述测试中未发现剩余错误；验证基于内存模拟网络，未做实网路由或吞吐测量。
未增加 ICMP 错误、动态路由、NAT 或多路径，这些不属于本阶段要求。
按用户“下一步是 point6”及此前代码、截图、文档和 push 的要求，
实现、验证与讲解由 Codex 辅助完成；未编造姓名、SUNet ID、耗时或到课记录。
