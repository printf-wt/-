Stanford CS 144 Networking Lab
==============================

These labs are open to the public under the (friendly, but also mandatory)
condition that to preserve their value as a teaching tool, solutions not
be posted publicly by anybody.

Website: https://cs144.stanford.edu

To set up the build system: `cmake -S . -B build`

To compile: `cmake --build build`

To run some tests (most tests are only available after pushing to the Stanford server): `cmake --build build --target check[checkpoint_num]`

or `cmake --build build --target test`

To run speed benchmarks: `cmake --build build --target speed`

To run clang-tidy (which suggests improvements): `cmake --build build --target tidy`

To format code: `cmake --build build --target format`

## 中文学习资料

- [Checkpoint 0–4 源码新手逐步讲解](writeups/check0-check4-source-code-guide.md)：逐函数讲解、状态手算、收发端完整推演、测量脚本与 23 份源码快照。

- [从环境配置到 Checkpoint 0、1、2、3、4、5、6 和 7](writeups/check0-4beginner-guide.md)：持续更新的新手指南，包含实际操作步骤、模块原理、示例、测试与 Git 提交流程。
- [Checkpoint 1 实现报告](writeups/check1.md)
- [Checkpoint 2 序号换算与 TCP 接收端](writeups/check2.md)：三种编号、确认号、接收窗口、实现步骤与验证记录。
- [Checkpoint 3 TCP 发送端](writeups/check3.md)：窗口发送、累计确认、超时重传、零窗口探测、代码截图与验证记录。
- [Checkpoint 4 真实网络测量](writeups/check4.md)：公网与同学路径的一小时测量、RTT/交付率图表及中文 PDF。
- [同学主机配置说明](writeups/check4-peer-setup.md)：Windows 查看 IP、限定来源的 ping 放行与实验后清理。

- [Checkpoint 5 网络接口与 ARP](writeups/check5.md)：下一跳地址解析、以太网封装、缓存过期、实际截图与测试结果。
- [Checkpoint 5 源码新手讲解](writeups/check5-source-code-guide.md)：逐函数解释、手算流程与两份完整源码。
- [Checkpoint 6 IPv4 路由器](writeups/check6.md)：最长前缀匹配、TTL、首部校验和、实际截图与测试记录。
- [Checkpoint 6 源码新手讲解](writeups/check6-source-code-guide.md)：逐函数解释、路由表手算与完整源码。
- [Checkpoint 7 全栈与迷你聊天室](writeups/check7.md)：本机全栈与三机双向 1 MiB 校验通过，含 PDF、截图和实测记录。
- [Checkpoint 7 源码新手讲解](writeups/check7-source-code-guide.md)：封装层次、自动实验、聊天协议、文件校验及源码快照。
- [当前三机联调记录](writeups/check7-session-2026-11-25.md)：新网络地址和当前进度。
