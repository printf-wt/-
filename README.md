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

## 中文学习入口

- [实验资料导航](writeups/README.md)：按 Point 0-7 查报告、源码讲解、截图与联调说明。
- [从环境配置到 Point 7](writeups/guides/beginner-guide.md)：新手按顺序学习的入口。
- [Checkpoint 0 到 7 源码新手逐步讲解](writeups/guides/check0-7-source-code-guide.md)：TCP、ARP、路由、聊天室与文件校验的统一教程，含全流程推演和完整源码附录。
- [最终 PDF 与离线包](output/README.md)：可提交、可分享的正式成果。
- [目录说明与旧路径对照](writeups/directory-layout.md)：整理规则、原始记录位置和验证命令。

## 目录用途

| 目录 | 内容 |
|---|---|
| `src/` | ByteStream、TCP、ARP 与 IPv4 路由等协议实现 |
| `apps/`、`util/` | 网络应用与框架基础工具 |
| `tests/`、`etc/`、`scripts/` | 官方测试、构建配置与框架脚本 |
| `tools/checkN/` | 测量、聊天、转发和补充验证程序 |
| `writeups/checkN/` | 对应实验的报告、截图、日志、原始数据和统计结果 |
| `writeups/guides/` | 跨实验的新手教程 |
| `output/checkN/` | 正式 PDF 与离线交付包 |
| `build/` | 本地编译、临时实验及报告预览，Git 忽略 |

## 本机 Ubuntu 构建

Windows 下用 WSL Ubuntu 构建 C++ 程序；在仓库根目录运行：

```bash
cmake -S . -B build/wsl -DSANITIZED_APPS=True
cmake --build build/wsl --parallel 4
ctest --test-dir build/wsl --output-on-failure --parallel 4
```

Python 文档链接和原始证据检查：`python3 tools/validate_layout.py`。
Point 7 的应用构建及本机复现命令见 [tools/check7/README.md](tools/check7/README.md)。

## 中文学习入口

- [实验资料导航](writeups/README.md)：按 Point 0-7 查报告、源码讲解、截图与联调说明。
- [从环境配置到 Point 7](writeups/guides/beginner-guide.md)：新手按顺序学习的入口。
- [最终 PDF 与离线包](output/README.md)：可提交、可分享的正式成果。
- [目录说明与旧路径对照](writeups/directory-layout.md)：整理规则、原始记录位置和验证命令。

## 目录用途

| 目录 | 内容 |
|---|---|
| `src/` | ByteStream、TCP、ARP 与 IPv4 路由等协议实现 |
| `apps/`、`util/` | 网络应用与框架基础工具 |
| `tests/`、`etc/`、`scripts/` | 官方测试、构建配置与框架脚本 |
| `tools/checkN/` | 测量、聊天、转发和补充验证程序 |
| `writeups/checkN/` | 对应实验的报告、截图、日志、原始数据和统计结果 |
| `writeups/guides/` | 跨实验的新手教程 |
| `output/checkN/` | 正式 PDF 与离线交付包 |
| `build/` | 本地编译、临时实验及报告预览，Git 忽略 |

## 本机 Ubuntu 构建

Windows 下用 WSL Ubuntu 构建 C++ 程序；在仓库根目录运行：

```bash
cmake -S . -B build/wsl -DSANITIZED_APPS=True
cmake --build build/wsl --parallel 4
ctest --test-dir build/wsl --output-on-failure --parallel 4
```

Python 文档链接和原始证据检查：`python3 tools/validate_layout.py`。
Point 7 的应用构建及本机复现命令见 [tools/check7/README.md](tools/check7/README.md)。
