# 实验资料导航

第一次阅读从[环境配置与实验入门](guides/beginner-guide.md)开始；想理解实现，先看[Point 0-4 源码讲解](guides/check0-4-source-code-guide.md)，再按下表进入后续实验。

| 实验 | 主要内容 | 实验报告 | 源码讲解与操作说明 |
|---|---|---|---|
| Point 0 | HTTP 获取与字节流 | [报告](check0/report.md) | [Point 0-4 源码讲解](guides/check0-4-source-code-guide.md) |
| Point 1 | 乱序字节重组 | [报告](check1/report.md) | [Point 0-4 源码讲解](guides/check0-4-source-code-guide.md) |
| Point 2 | 序号换算与 TCP 接收端 | [报告](check2/report.md) | [Point 0-4 源码讲解](guides/check0-4-source-code-guide.md) |
| Point 3 | TCP 发送端与超时重传 | [报告](check3/report.md) | [Point 0-4 源码讲解](guides/check0-4-source-code-guide.md) |
| Point 4 | 真实网络测量 | [报告](check4/report.md) | [同学主机配置](check4/peer-setup.md) |
| Point 5 | 网络接口与 ARP | [报告](check5/report.md) | [源码讲解](check5/source-code-guide.md) |
| Point 6 | IPv4 路由器 | [报告](check6/report.md) | [源码讲解](check6/source-code-guide.md) |
| Point 7 | 全栈网络、聊天与文件校验 | [报告](check7/report.md) | [源码讲解](check7/source-code-guide.md) · [三机启动](check7/peer-setup.md) |

每个 `checkN` 目录按用途组织，只有实际需要的目录才会创建：

- `report.md`：实验做了什么、结果是什么。
- `source-code-guide.md`：逐步解释实现。
- `screenshots/`：真实代码截图；手动截取的图片也保留在这里。
- `logs/`：测试日志、构建日志与验证摘要。
- `data/`：原始测量、抓包及实测记录，保留原始字节。
- `results/`：从测量数据生成的统计和图表。
- `sessions/`：按日期保存的联调过程，历史地址不直接复用于新网络。

最终可分享的 PDF 和离线包见[成果目录](../output/README.md)。辅助程序及补充验证脚本在 `tools/checkN/`。整理规则和旧路径对照见[目录说明](directory-layout.md)。
