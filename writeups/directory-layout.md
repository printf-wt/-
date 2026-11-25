# 项目目录说明

整理日期：2026-11-25。

本机项目根目录已从 `-` 改名为 `cs144-network-lab`。外层的八份实验 PDF 已移至 `references/assignments/`，课程设计 Word 指导书移至 `references/course-design/`，外层另有导航 README。这些是仓库之外的本地参考资料。

Windows 项目路径为 `D:\计算机网络\课程设计\cs144-network-lab`，WSL 路径为 `/mnt/d/计算机网络/课程设计/cs144-network-lab`。旧 `build/wsl/` 完整保留在 `build/legacy-wsl-before-rename-20261125/`，新路径下重新配置 `build/wsl/`；历史日志中的旧绝对路径保留。

## 去哪里找文件

| 想做的事 | 位置 |
|---|---|
| 理解从环境安装到 Point 7 的过程 | [新手指南](guides/beginner-guide.md) |
| 阅读各实验报告、学习源码 | [实验导航](README.md) |
| 阅读或修改协议实现 | `src/` |
| 阅读官方应用或底层工具 | `apps/`、`util/` |
| 运行官方测试 | `tests/`，命令见项目 README |
| 运行测量、聊天、UDP 转发或补充检查 | `tools/checkN/` |
| 查截图、测试日志、原始数据 | `writeups/checkN/` 下的对应子目录 |
| 获取最终 PDF 或离线包 | [成果目录](../output/README.md) |
| 找编译产物、PDF 预览或临时实验输出 | `build/`；本地 IDE 还可能创建 `out/`、`.vs/` |

源码目录保持官方工程结构。`build/`、`out/`、`.vs/` 是本地生成目录，已由 Git 忽略；`output/` 保存正式成果，需要提交 Git。临时输出应进入 `build/`，避免与正式成果混放。

## 旧路径对照

| 原位置 | 整理后 |
|---|---|
| `writeups/checkN.md` | `writeups/checkN/report.md` |
| `writeups/checkN-source-code-guide.md` | `writeups/checkN/source-code-guide.md` |
| `writeups/checkN-peer-setup.md` | `writeups/checkN/peer-setup.md` |
| `writeups/checkN-screenshots/*.jpg`、`*.png` | `writeups/checkN/screenshots/` |
| `writeups/checkN-screenshots/*.log`、`validation.txt` | `writeups/checkN/logs/` |
| `writeups/checkN-screenshots/*.py` | `tools/checkN/` |
| `writeups/checkN-data/` | `writeups/checkN/data/` |
| `writeups/check4-results/` | `writeups/check4/results/` |
| `writeups/check0-4beginner-guide.md` | `writeups/guides/beginner-guide.md`，内容已覆盖 Point 0-7 |
| `writeups/check0-check4-source-code-guide.md` | `writeups/guides/check0-4-source-code-guide.md` |
| `writeups/check7-progress.md` | `writeups/check7/sessions/2026-11-24.md` |
| `writeups/check7-session-2026-11-25.md` | `writeups/check7/sessions/2026-11-25.md` |
| `output/pdf/checkN-report.pdf` | `output/checkN/report.pdf` |

原始数据、旧运行日志和已经交付的 ZIP 按字节保留；这些文件中出现的旧路径是当时的运行环境。Point 0-4 教程附录的源码快照保留基准提交内容，运行当前版本时使用正文的新路径和实际工具文件。

整理同步更新了报告生成器、默认数据路径、文档链接和 Git 属性。Point 7 数据清单仅改变路径键，原始文件哈希保持一致；PDF 会从相同数据重新生成。

## 检查目录和报告

从仓库根目录运行：

```bash
python3 tools/validate_layout.py
python3 tools/check7/validate.py
```

前者只读检查 Markdown 本地链接、截图分类和已有数据哈希；后者核对已保存实验的协议首部、文件校验、测试日志，并重新生成 Point 7 数据清单。

Windows 已配置中文字体与 ReportLab 时，可重新生成正式报告：

```powershell
python -X utf8 tools/check4/build_report.py writeups/check4/results/cloudflare writeups/check4/results/google writeups/check4/results/classmate --peer 172.20.10.2
python -X utf8 tools/check7/build_report.py
```

`172.20.10.2` 是 Point 4 已保存测量的历史同学地址；生成报告只读取现有结果，不连接该主机。PDF 更新后还应渲染检查版面。

## 本次整理验收

- 24 份 Markdown 的 237 个本地链接检查通过；截图目录只包含图片。
- Point 7 的 59 份原始证据哈希一致，清单只更新路径键；四种本机拓扑与真实三机记录的验证通过。
- 189 个迁移的原始记录、日志、图片和统计文件保持原工作区字节；其暂存内容也与迁移前 Git 版本逐份核对一致。
- 项目改名后，WSL 新构建目录重新配置成功，官方 CTest 40/40 通过，两个完整网络栈应用重新编译成功。
- 移至 `tools/check2/`、`check3/`、`check5/`、`check6/` 的四组补充验证重新运行通过，共 26 个场景，启用 ASan/UBSan。
- 测量统计测试 10/10、聊天协议测试 8/8 通过。
- Point 4 和 Point 7 报告重新生成，仍分别为 10 页和 6 页；所有页面已渲染检查。

本次只整理文件、更新路径和导航，不修改协议实现。整理前已有的未提交源码修改与手动截图保留原来的未提交状态。新路径的编译与补充验证日志留在本机 `build/layout-validation/`，历史实验日志保留在各实验的 `logs/`。
