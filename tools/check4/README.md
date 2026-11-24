# Checkpoint 4 网络测量工具

本阶段是网络测量，不新增 C++ 框架，也没有 check4 构建目标。
Python 3.10 及以上可运行统计代码；采集需要 Ubuntu/WSL 的 iputils ping。
分析和 PDF 可以在 Windows Python 中执行，与 C++ 的 Ubuntu 编译环境分开。
依赖文件记录本次实际使用的 matplotlib 和 reportlab 版本。

## 1 采集一小时

在 Ubuntu 的项目根目录执行，整个测量期间保持电脑联网且不休眠：

```bash
cd "/mnt/d/计算机网络/课程设计/-"
python3 tools/check4/collect.py 1.1.1.1 --output build/my-check4/cloudflare --duration 3602
```

目标可以替换为已确认可达的同学 IP，每次使用新的输出目录。
普通测量默认为每 0.2 秒发送 56 字节载荷，不能把采集间隔改得更小。
脚本保存原始 ping.txt 和 metadata.json；后者记录真实开始、结束和经过时间。
中断采集会标为 interrupted，子进程提前退出会标为 ended_early；最终报告拒绝未完成或不足一小时的测量。
一组不得跨越 65,535 个序号，否则应拆成多个会话单独分析。

采集期间可以在另一个 Windows PowerShell 窗口查看进度，不会中断测量：

```powershell
python tools/check4/status.py
```

输出包含已运行与剩余分钟数、当前观测到的回复/序号数和最近回复时间。
只有最终 ping 汇总出现之后，发送数才是完整测量的最终数值。

## 2 短时速率实验

在 Ubuntu 项目根目录执行：

```bash
python3 tools/check4/burst.py 1.1.1.1 --output build/my-check4/cloudflare/bursts
```

三档配置为 56 字节/0.2 秒、256 字节/0.1 秒、1200 字节/0.05 秒；
每组均有 8 秒截止时间。ping 同时设置 -c 和 -w 时可能为等待目标回复数继续发送，
因此统计始终使用最终实际发送数，而不是命令中的请求计数。
trials.json 记录实际总时长、收发数量和名义速率、观测速率。
速率只统计载荷，不包含 IP、ICMP 或链路层开销，不当作线路容量。

## 3 路由探测

在 Windows PowerShell 中执行，以下命令不会更改路由：

```powershell
tracert -d -h 24 -w 250 1.1.1.1
```

星号表示对应探测没有及时得到回复，不等于后续数据无法通过该跳。
仅有 IP、私网跳点或大量星号时，不能据此断言具体城市、国家或完整路径。
本次 Windows tracert 输出随原始数据保存；WSL 环境可能影响可观察的跳点。

## 4 分析与绘图

在 Windows PowerShell 的项目根目录执行：

```powershell
python -m pip install -r tools/check4/requirements.txt
python tools/check4/test_metrics.py
python tools/check4/analyze.py build/my-check4/cloudflare --output build/my-check4-results/cloudflare
```

Ubuntu 中安装相同依赖后，也能用 python3 分析。
采集期间可以显式加 --preview 输出带预览标记的临时结果；预览不能代替最终报告。

| 输出 | 含义 |
|---|---|
| statistics.json | 总发送数、唯一回复数、交付率、连续成功/失败长度、RTT 与条件概率 |
| probes.csv | 每个序号一行；未回复的 RTT 留空，不填 0 |
| conditional.csv | k=-10..10 的两个条件概率及各自有效分母 |
| rtt-time.png/.pdf | RTT 随回复实际时刻变化，时间标为 UTC+8 |
| rtt-cdf.png/.pdf | 成功样本的经验累计分布 |
| conditional.png/.pdf | 成功/丢失的条件概率及无条件基线 |
| adjacent-rtt.png/.pdf | 仅使用 N 和 N+1 都成功的 RTT 散点 |
| rate-trials.png/.pdf | 三档短时试验中的实际请求与回复载荷速率 |

统计使用最终汇总的发送数，包含首尾没有回复的探测。
-O 的“no answer yet”只是当时仍在等待；后续收到回复时仍算成功。
重复回复只计一次，乱序回复按序号恢复。
逐行 RTT 的显示位数由 ping 决定，本报告不会把显示值当成更高精度的测量。
time<1 等记录保留上界并单独计数。

令 S[n] 为第 n 次探测是否成功：

```text
交付率 = 成功序号数 / 最终发送数
P(S[n+k]=1 | S[n]=1) = 两次均成功的有效序号对数 / 首次成功的有效序号对数
P(S[n+k]=0 | S[n]=0) = 两次均丢失的有效序号对数 / 首次丢失的有效序号对数
```

只取 n 与 n+k 都在样本范围内的组合，分母随 k 改变。
没有丢失时，第二个概率未定义，不能写成 0。
k=0 时条件概率必然为 1，也不能用这根柱子证明存在突发性。

## 5 生成中文报告

可以把两条或更多完成的路径一起交给报告脚本，例如在 Windows PowerShell 中：

```powershell
python tools/check4/build_report.py writeups/check4-results/cloudflare writeups/check4-results/google
```

默认输出 writeups/check4.md 与 output/pdf/check4-report.pdf。
脚本优先使用 Windows 黑体或微软雅黑；Linux 可用文泉驿正黑字体，
也可通过 --font 指定支持中文的 TrueType 字体路径。

测完同学路径后，把对应结果目录也加在命令中，并用 --peer 填入本次实际测量的同学 IP。
这只标注现有数据的身份，不会创建缺失的测量数据。
默认报告要求各条路径均已结束、具有最终 ping 汇总且真实采集时长不少于 3600 秒。

## 6 文件职责与测试

| 文件 | 职责 |
|---|---|
| collect.py | 低频长时采集、命令与时间元数据 |
| status.py | 查看进度与最近回复，不改变采集进程或原始数据 |
| burst.py | 有界短时速率试验及原始输出 |
| metrics.py | 纯统计与日志解析，不依赖绘图库 |
| analyze.py | CSV、JSON、图表与原始日志 SHA-256 |
| build_report.py | 从结果生成中文 Markdown 与 PDF |
| test_metrics.py | 统计边界测试，使用明确的人工测试数据 |
| test_lifecycle.py | Ubuntu 回环上的真实进程中断检查 |

测试数据仅用于验证统计函数，未混入实测日志或图表。
源码截图另保存在 writeups/check4-screenshots；截图来自实际编辑器窗口。

参考：[官方实验要求](https://cs144.github.io/assignments/check4.pdf)、
[iputils ping 参数](https://man7.org/linux/man-pages/man8/ping.8.html)。

## 7 本次重试数据

更换局域网后，重新采集的数据位于 writeups/check4-data/network2。
查看本次进度：

```powershell
python tools/check4/status.py --root writeups/check4-data/network2
```

原目录三条测量不足一小时，仅作历史记录保留。
本次正式分析、图表与报告只使用 network2 中完成的会话。

Ubuntu 中运行 `python3 tools/check4/test_lifecycle.py` 可复现采集提前退出与主动中断检查。
