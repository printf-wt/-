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

- [从环境配置到 Checkpoint 0、1 和 2](writeups/check0-check1-beginner-guide.md)：持续更新的新手指南，包含实际操作步骤、模块原理、示例、测试与 Git 提交流程。
- [Checkpoint 1 实现报告](writeups/check1.md)
- [Checkpoint 2 序号换算与 TCP 接收端](writeups/check2.md)：三种编号、确认号、接收窗口、实现步骤与验证记录。
