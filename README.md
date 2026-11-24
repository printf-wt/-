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

- [从环境配置到 Checkpoint 0、1、2、3 和 4](writeups/check0-check1-beginner-guide.md)：持续更新的新手指南，包含实际操作步骤、模块原理、示例、测试与 Git 提交流程。
- [Checkpoint 1 实现报告](writeups/check1.md)
- [Checkpoint 2 序号换算与 TCP 接收端](writeups/check2.md)：三种编号、确认号、接收窗口、实现步骤与验证记录。
- [Checkpoint 3 TCP 发送端](writeups/check3.md)：窗口发送、累计确认、超时重传、零窗口探测、代码截图与验证记录。
- [Checkpoint 4 真实网络测量](writeups/check4.md)：公网与同学路径的一小时测量、RTT/交付率图表及中文 PDF。
- [同学主机配置说明](writeups/check4-peer-setup.md)：Windows 查看 IP、限定来源的 ping 放行与实验后清理。
