"""Build a source-backed Chinese Markdown and PDF report from analyzed paths."""

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                               Spacer, Table, TableStyle)


SOURCE_URL = "https://cs144.github.io/assignments/check4.pdf"
PING_URL = "https://man7.org/linux/man-pages/man8/ping.8.html"
LOCAL_TIME = timezone(timedelta(hours=8))


def number(value, digits=3):
    return "未定义" if value is None else f"{value:.{digits}f}"


def local_time(value):
    return datetime.fromisoformat(value).astimezone(LOCAL_TIME).strftime("%Y-%m-%d %H:%M:%S") if value else "采集中"


def relative_link(path, markdown):
    return Path(os.path.relpath(path, markdown.parent)).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("writeups/check4/report.md"))
    parser.add_argument("--pdf", type=Path, default=Path("output/check4/report.pdf"))
    parser.add_argument("--font", type=Path)
    parser.add_argument("--peer", help="Exact host/IP of the measured classmate path")
    parser.add_argument("--routes", type=Path, default=Path("writeups/check4/data/network2/routes"))
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    rows = [(path, json.loads((path / "statistics.json").read_text(encoding="utf-8"))) for path in args.results]
    if not args.preview and any(not stats["finalized"] or stats["collection_state"] != "finished"
                                or stats["elapsed_s"] < 3600 for _, stats in rows):
        raise ValueError("A final report requires finished measurements lasting at least one hour")
    if args.peer and not any(stats["host"] == args.peer for _, stats in rows):
        raise ValueError("The declared classmate path must be present in the analyzed results")
    has_peer = args.peer is not None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    candidates = ([args.font] if args.font else []) + [
        Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ]
    font = next((path for path in candidates if path and path.exists()), None)
    if font is None:
        raise ValueError("Provide --font pointing to a Chinese TrueType font (for example simhei.ttf)")
    pdfmetrics.registerFont(TTFont("ReportCJK", str(font)))
    body = ParagraphStyle("CJKBody", fontName="ReportCJK", fontSize=10, leading=16,
                          wordWrap="CJK", spaceAfter=7)
    title_style = ParagraphStyle("CJKTitle", parent=body, fontSize=20, leading=28,
                                 textColor=colors.HexColor("#183c61"), spaceAfter=16)
    heading = ParagraphStyle("CJKHeading", parent=body, fontSize=13, leading=20,
                             textColor=colors.HexColor("#183c61"), spaceBefore=8, spaceAfter=8)
    small = ParagraphStyle("CJKSmall", parent=body, fontSize=8, leading=12)
    markdown = []
    story = []

    def h(text, level=2):
        markdown.append("#" * level + " " + text + "\n")
        story.append(Paragraph(escape(text), title_style if level == 1 else heading))

    def p(text):
        markdown.append(text + "\n")
        story.append(Paragraph(escape(text), body))

    def table(headers, values, widths=None):
        markdown.extend(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)])
        markdown.extend("| " + " | ".join(map(str, row)) + " |" for row in values)
        markdown.append("")
        cells = [[Paragraph(escape(str(cell)), small) for cell in row] for row in [headers] + values]
        t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eff7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#527491")),
            ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#aab8c4")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([t, Spacer(1, 8)])

    def figure(path, caption, height):
        markdown.append(f"![{caption}]({relative_link(path, args.output)})\n")
        story.append(KeepTogether([Image(str(path), width=170 * mm, height=height * mm),
                                   Paragraph(escape(caption), small), Spacer(1, 7)]))

    label = "（采集中预览，不能作为最终结果）" if args.preview else ""
    h("Checkpoint 4：真实网络路径测量" + label, 1)
    p("本阶段测量 ICMP Echo 的交付与往返时间，不修改前面完成的 TCP 源码。"
      "实验、分析脚本和文档由 Codex 按用户请求辅助完成，原始数据随报告保留。")
    if has_peer:
        p(f"测量范围：{len(rows)} 条路径，其中同学主机路径为 {args.peer}。"
          "这条路径采用实际可达的网络环境，与课程 CS144 专用私网不同。")
    else:
        p("当前范围为公网路径测量。同学主机路径尚未完成，因此本报告不声称满足官方第二条路径要求。"
          "已保留追加同学路径的采集、分析及报告接口。")
    p("采集位置为本机 WSL2 Ubuntu，普通测量每 0.2 秒发送一个 56 字节 ICMP 载荷。"
      "图中时间为 UTC+08:00；原始时间戳与元数据使用 UTC。")
    table(["目标", "开始时间（UTC+8）", "采集时长（秒）", "已发 / 已收"],
          [[s["host"], local_time(s["started_utc"]), number(s["elapsed_s"], 2),
            f'{s["sent"]} / {s["received_unique"]}'] for _, s in rows],
          [30 * mm, 65 * mm, 35 * mm, 40 * mm])
    h("统计口径")
    p("交付率使用唯一回复数除以最终发送数；首部、内部和末尾没有回复的序号均计入。"
      "这里的丢失表示测量截止时没有观察到 Echo Reply，可能包含过滤、限速和截止时尚在途的探测，"
      "不能直接等同于 TCP 丢包率。-O 的暂未回复提示不作为最终丢失判据。")
    p("RTT 使用每个成功序号首次收到的回复。相邻 RTT 只配对原始序号 N 与 N+1，"
      "不会跨越丢包拼接。条件概率只使用两端均在样本范围内的序号对，分母同时导出；"
      "条件事件没有样本时记为未定义。k=0 的条件概率为 1，不代表时间相关性证据。")
    p("逐探测 RTT 的精度受 ping 输出位数限制，补齐的小数位不表示测量精度提高。"
      "原始汇总可能保留更多小数位；time<1 之类的记录按显示上界纳入，并单独记录数量。")
    p("每秒 5 次、一小时的理论探测数为 18,000；实际次数以 ping 汇总为准，"
      "会受调度和实际间隔影响。官方说明中的 3,600 次与其给出的频率不相符。")
    table(["目标", "交付率", "最长连续成功 / 失败", "RTT 最小 / 中位 / 最大（ms）"],
          [[s["host"], f'{s["delivery_rate"]:.3%}',
            f'{s["longest_success_run"]} / {s["longest_loss_run"]}',
            f'{number(s["rtt_min_ms"], 1)} / {number(s["rtt_median_ms"], 1)} / {number(s["rtt_max_ms"], 1)}']
           for _, s in rows], [30 * mm, 28 * mm, 46 * mm, 66 * mm])

    for directory, stats in rows:
        story.append(PageBreak())
        h(f'{stats["host"]}：RTT 的时间变化与分布', 1)
        p(f'平均 RTT 为 {number(stats["rtt_mean_ms"])} ms，95% 分位数为 {number(stats["rtt_p95_ms"])} ms。'
          f'最小值 {number(stats["rtt_min_ms"])} ms 是本次样本的最小往返时间，不等于精确传播时延。')
        figure(directory / "rtt-time.png", "RTT 随回复时刻的变化；缺失回复没有 RTT，未填成零。", 66.6)
        figure(directory / "rtt-cdf.png", "经验累计分布：横轴给定 RTT，纵轴是 RTT 不超过它的成功样本比例。", 66.6)
        if stats["rtt_p95_ms"] is not None and stats["rtt_max_ms"] > stats["rtt_p95_ms"] * 1.5:
            p("最大 RTT 明显高于 95% 分位数，说明主体样本之外存在较高时延的右尾。"
              "仅凭 ping 不能把这些尖峰归因于某一个路由器或某一种排队机制。")
        story.append(PageBreak())
        h(f'{stats["host"]}：丢失与 RTT 的相关性', 1)
        figure(directory / "conditional.png", "k 从 -10 到 10；虚线是无条件概率，柱高使用各自有效样本分母。", 101)
        figure(directory / "adjacent-rtt.png", "仅使用连续两个探测均成功的序号对绘制散点。", 80.4)
        loss_next = stats["conditional"][11]
        p(f'P(下一次仍丢失 | 本次丢失) = {number(loss_next["loss_probability"])}，'
          f'分母为 {loss_next["loss_denominator"]}；无条件丢失率为 {1 - stats["delivery_rate"]:.3%}。'
          '有限样本中条件概率高于基线可提示损失聚集，不据此宣称统计显著。')

    story.append(PageBreak())
    h("短时速率实验与路径观察", 1)
    p("每条路径分别进行 56 字节/0.2 秒、256 字节/0.1 秒和 1200 字节/0.05 秒的短时试验。"
      "每组设置 8 秒截止时间。图中速率只计算 ICMP 载荷，不含 IP、ICMP 和链路层头部，"
      "请求和回复均除以该组相同的实际总时长。短时试验与长时采集有重叠，时间记录在 trials.json。")
    for index, (directory, stats) in enumerate(rows):
        rate = directory / "rate-trials.png"
        if index and index % 2 == 0:
            story.append(PageBreak())
            h("短时速率实验与路径观察（续）", 1)
        if rate.exists():
            figure(rate, f'{stats["host"]}：有限三档探测负载下的收发速率。', 62)
        trials = stats.get("burst_trials", [])
        if trials:
            best = max(trials, key=lambda trial: trial["observed_reply_payload_bps"])
            p(f'{stats["host"]} 本次最大观测回复载荷速率为 '
              f'{best["observed_reply_payload_bps"] / 1000:.3f} kbit/s，'
              f'对应 {best["payload_bytes"]} 字节、间隔 {best["interval_s"]} 秒的配置；'
              f'实际收到 {best["received"]}/{best["sent"]} 个回复，总时长 {best["elapsed_s"]:.3f} 秒。')
    p("这三档负载只能比较本次试验中的回复速率；即使没有平台期，也不能认定达到或测出了线路容量。"
      "较高回复速率是已测试配置的观测最大值，不是 TCP 吞吐或下载带宽。")
    p(f"本次 Windows tracert 原始输出保存在 {args.routes.as_posix()}。公网路径从 172.20.10.1 网关出发，"
      "中间可见部分公网跳点，同时有不回复 TTL 探测的跳点。仅凭这些数字地址不能还原完整地理路线，"
      "也不能确认经过的城市或国家；目标 IP 的服务商所在地不能代替实际路径地理证据。")
    if has_peer:
        p("本次同学路径经 Windows tracert 观察为一跳到达目标，与公网路径的输出明显不同。"
          "这一结果描述可观察的 IP 跳点，不表示中间没有交换机、无线设备或其他二层设施。")
    story.append(PageBreak())
    h("路径比较、复现与数据完整性", 1)
    ordered = sorted(rows, key=lambda item: item[1]["rtt_median_ms"] if item[1]["rtt_median_ms"] is not None else float("inf"))
    if len(ordered) > 1:
        p(f'本次中位 RTT 最低的路径为 {ordered[0][1]["host"]}。'
          '不同目标的差异包含出口、远端回复策略以及时段影响，不能只解释为物理距离差异。'
          '共享前段跳点和同机并行采集也意味着这些路径不是完全独立的重复实验。')
    p("采集脚本使用 Linux ping；分析和绘图需要 Python 与 matplotlib；PDF 额外需要 reportlab 和中文 TrueType 字体。"
      "在仓库根目录运行 python tools/check4/test_metrics.py 可验证统计口径。"
      "运行命令、字段含义和添加同学路径的方法见 tools/check4/README.md 与新手指南。")
    for directory, stats in rows:
        p(f'{stats["host"]} 原始 ping.txt 的 SHA-256：{stats["source_sha256"]}')
        markdown.append(f'- [逐探测数据]({relative_link(directory / "probes.csv", args.output)})；'
                        f'[统计 JSON]({relative_link(directory / "statistics.json", args.output)})；'
                        f'[条件概率及分母]({relative_link(directory / "conditional.csv", args.output)})\n')
    h("参考说明")
    p("课程要求与分析项目以官方 Checkpoint 4 说明为依据；命令参数以 iputils ping 手册为依据。"
      "本报告保留原始数据和方法边界，不补造无法从日志确认的地理路线或实验结果。")
    story.append(Paragraph(f'<link href="{SOURCE_URL}" color="#2463a6">CS144 Checkpoint 4</link>', small))
    story.append(Paragraph(f'<link href="{PING_URL}" color="#2463a6">iputils ping manual</link>', small))
    markdown.extend([f'- [CS144 Checkpoint 4]({SOURCE_URL})', f'- [ping 参数说明]({PING_URL})',
                     f'- [PDF 报告]({relative_link(args.pdf, args.output)})', ""])
    markdown.extend([
        '## 实现、配置与代码截图\n',
        '- [测量工具与复现命令](../../tools/check4/README.md)',
        '- [同学 Windows 主机配置记录](peer-setup.md)',
        '- [持续更新的新手指南](../guides/beginner-guide.md)',
        '- [验证记录](logs/validation.txt)\n',
        '![采集命令与实际计时](screenshots/01-collector.jpg)\n',
        '![最终发送数、去重与完整性检查](screenshots/02-ping-parser.jpg)\n',
        '![条件概率分母与相邻序号配对](screenshots/03-conditional-and-adjacent.jpg)\n',
    ])
    args.output.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("ReportCJK", 8)
        canvas.setFillColor(colors.HexColor("#526574"))
        canvas.drawString(20 * mm, 12 * mm, "CS144 / Checkpoint 4 / 实测数据报告" + (" / 预览" if args.preview else ""))
        canvas.drawRightString(190 * mm, 12 * mm, str(doc.page))
        canvas.restoreState()

    document = SimpleDocTemplate(str(args.pdf), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                                 topMargin=18 * mm, bottomMargin=20 * mm,
                                 title="CS144 Checkpoint 4 网络测量报告", author="Codex-assisted course project")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Wrote {args.output} and {args.pdf}")


if __name__ == "__main__":
    main()
