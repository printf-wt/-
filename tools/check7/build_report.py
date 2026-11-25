"""Build the Point 7 report from saved experiment results, without inventing peer outcomes."""

import argparse
from html import escape
import json
from pathlib import Path
import subprocess

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=ROOT / "output/pdf/check7-report.pdf")
    parser.add_argument("--markdown", type=Path, default=ROOT / "writeups/check7.md")
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/simhei.ttf"))
    parser.add_argument("--peer-config", type=Path,
                        default=ROOT / "writeups/check7-data/three-host-2026-11-25/attempt-01/config.json")
    args = parser.parse_args()
    peer_config = json.loads(args.peer_config.read_text(encoding="utf-8"))
    peer_result = None
    if peer_config.get("three_host_verified"):
        peer_result = json.loads((args.peer_config.parent / peer_config["verification_file"]).read_text(encoding="utf-8"))
        received = peer_result["received_file_verifications"]
        if (peer_result["status"] != "passed" or len(received) != 2
                or not all(item["size"] == 1_048_576 and item["sha256"] == peer_result["expected_sha256"]
                           for item in received)
                or len({item["saved_as"] for item in received}) != 2):
            raise ValueError("Three-host receipt evidence does not support a pass")
    names = ["tiny-final", "bigger", "loss", "chat"]
    runs = {name: json.loads((ROOT / "writeups/check7-data" / name / "results.json").read_text(encoding="utf-8"))
            for name in names}
    for name, run in runs.items():
        if run["status"] != "passed" or not run["transfers"] or not all(t["match"] for t in run["transfers"]):
            raise ValueError("Cannot report this experiment as passed: " + name)
    pdfmetrics.registerFont(TTFont("CJK", str(args.font)))
    body = ParagraphStyle("Body", fontName="CJK", fontSize=10, leading=16, wordWrap="CJK", spaceAfter=9)
    heading = ParagraphStyle("Heading", parent=body, fontSize=14, leading=21, spaceBefore=12,
                             textColor=colors.HexColor("#174b70"), keepWithNext=True)
    title = ParagraphStyle("Title", parent=heading, fontSize=23, leading=31, spaceAfter=16)
    small = ParagraphStyle("Small", parent=body, fontSize=8, leading=12)
    mono = ParagraphStyle("Code", parent=small, fontName="Courier", fontSize=7, leading=11,
                          backColor=colors.HexColor("#f0f4f8"), borderPadding=7, spaceAfter=10)
    story, markdown = [], []

    def h(text, level=2):
        markdown.append("#" * level + " " + text + "\n")
        story.append(Paragraph(escape(text), title if level == 1 else heading))

    def p(text):
        markdown.append(text + "\n")
        story.append(Paragraph(escape(text), body))

    def table(headers, rows, widths):
        markdown.extend(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)])
        markdown.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
        markdown.append("")
        cells = [[Paragraph(escape(str(cell)), small) for cell in row] for row in [headers, *rows]]
        grid = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5eef5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#527491")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([grid, Spacer(1, 8)])

    def topology():
        drawing = Drawing(490, 145)
        positions = {"C1": (10, 90), "C2": (10, 20), "R1": (115, 55), "R2": (220, 55),
                     "R3": (325, 55), "S1": (420, 90), "S2": (420, 20)}
        for left, right in [("C1", "R1"), ("C2", "R1"), ("R1", "R2"), ("R2", "R3"), ("R3", "S1"), ("R3", "S2")]:
            x1, y1 = positions[left]; x2, y2 = positions[right]
            drawing.add(Line(x1 + 24, y1 + 15, x2 + 24, y2 + 15, strokeColor=colors.HexColor("#6487a3")))
        for label, (x, y) in positions.items():
            drawing.add(Rect(x, y, 48, 30, fillColor=colors.HexColor("#e5eef5"), strokeColor=colors.HexColor("#174b70")))
            drawing.add(String(x + 24, y + 10, label, fontName="Helvetica-Bold", fontSize=11, textAnchor="middle"))
        drawing.add(String(160, 112, "10.0.12.0/24", fontName="Helvetica", fontSize=9))
        drawing.add(String(269, 112, "10.0.23.0/24", fontName="Helvetica", fontSize=9))
        story.append(drawing)
        markdown.extend(["```text", "C1 (80/8) -- R1 -- R2 -- R3 -- S1 (50/8)",
                         "C2 (81/8) --/             \\-- S2 (51/8)", "```\n"])

    h("Checkpoint 7：全栈网络与迷你聊天室", 1)
    p("本机实验证据与三机联调记录 | " + peer_config["client_date"])
    p("当前状态：本机全栈、多路由并发、定点丢包恢复及创意应用已验证；三台真实电脑之间的 UDP、双向 TCP 数据与各 1 MiB 接收文件校验通过。" if peer_result else
      "当前状态：已完成本机全栈、多路由并发、定点丢包恢复和创意应用；跨三台电脑的互通仍在验证，尚未记录通过。")
    h("1. 范围与证据")
    p("官方 Point 7 要求端点与路由器整合、三人联网、更大拓扑及创意项目。本机使用官方 tcp_eth_udp/fun_router，运行独立 C++ 进程和真实 Linux UDP 套接字；外层物理网络仅为 127.0.0.1。它比模块模拟进一步，但不等同于三位同学跨电脑互通。")
    starter = subprocess.check_output(["git", "rev-parse", "upstream/check7-startercode"], cwd=ROOT, text=True).strip()
    p("官方框架提交：" + starter + "。应用使用 ASan/UBSan；未新增名为 check7 的空测试目标。")
    result_rows = [
        ["一台路由器", "1 条 TCP / 2 方向", runs["tiny-final"]["bytes_per_direction"], "SHA-256 与逐字节均一致"],
        ["三台路由器", "2 条并发 TCP / 4 方向", runs["bigger"]["bytes_per_direction"], "全部一致"],
        ["定点丢包", "丢 1 个带数据以太网帧", runs["loss"]["bytes_per_direction"], "重传后双向一致"],
        ["聊天室", "双向消息及文件", runs["chat"]["bytes_per_direction"], "消息、接收文件及校验均一致"],
    ]
    if peer_result:
        result_rows.append(["三台电脑实测", "1 条 TCP / 2 方向", 1_048_576, "两个接收端大小及 SHA-256 均一致"])
    table(["实验", "连接/方向", "每方向字节", "数据校验"], result_rows, [105, 120, 90, 160])
    p("1 MiB = 1,048,576 字节。四次本机自动实验各约 30 秒，含连接与关闭等待，不作为网络吞吐基准；不将这些时长套用到三机实测。初次失败记录也保留，成功表格只引用核对通过的记录。")
    story.append(PageBreak())
    h("2. 本机更大拓扑与路由")
    topology()
    p("所有节点运行在同一 WSL 中。四个端点是 C1=80.6.5.4、C2=81.6.5.4、S1=50.9.8.7、S2=51.9.8.7。C1 <-> S1 与 C2 <-> S2 同时传输。R1-R2 的接口为 10.0.12.1/10.0.12.2，R2-R3 为 10.0.23.2/10.0.23.3。")
    table(["节点", "直连路由", "其他目标的下一跳"], [
        ["R1", "80/8→client1；81/8→client2", "50/8、51/8→east，经 10.0.12.2"],
        ["R2", "中间转发", "80/8、81/8→west，经 10.0.12.1；50/8、51/8→east，经 10.0.23.3"],
        ["R3", "50/8→server1；51/8→server2", "80/8、81/8→west，经 10.0.23.2"],
    ], [45, 160, 270])
    p("端点分别以各自所在网络的 .0.0.1 为默认虚拟网关。每条路由及动态分配的物理 UDP 端口都完整记录在 bigger/results.json 的 routers、endpoints、commands 和 links 中。")
    p("帧记录显示源端 TTL=128，经过三台路由器后抵达端点的 TTL=125。中间两段链路观测到 127 与 126，符合逐跳减一。该结果来自代理实际收到的数据，不是手填的示意值。")
    h("3. 双向文件完整性")
    for transfer in sorted(runs["tiny-final"]["transfers"], key=lambda item: item["node"]):
        p(transfer["node"] + " 接收 " + str(transfer["received_bytes"]) + " 字节，SHA-256：")
        story.append(Paragraph(transfer["sha256"], mono))
        markdown.append("```text\n" + transfer["sha256"] + "\n```\n")
    story.append(PageBreak())
    h("4. 抓帧与丢包恢复")
    p("为避免抓系统网卡权限依赖，本机实验在外层 UDP 隧道代理处记录内层以太网帧，写入标准 Ethernet pcap。每帧最多保存 96 字节，原始帧长度也保留；这可检查 ARP、IP/TCP 首部，不能用来重建完整文件。")
    loss_link = next(link for link in runs["loss"]["links"] if link["dropped_data_frames"])
    p("定点丢包位置：" + loss_link["name"] + " 链路，主动丢弃 " + str(loss_link["dropped_data_frames"]) +
      " 帧。该链路观测到重复的数据序号范围 " + str(loss_link["repeated_data_ranges"]) +
      " 次，随后两个接收文件都与预期一致。这里只主动丢一次，不把它描述为固定百分比丢包实验。")
    p("正常回环运行也可见个别重复序号范围；它们可能对应本机调度和超时重传，不能将未注入丢包解释为绝无重传。实验工具没有代替 TCP 补发数据。")
    h("5. 创意项目：聊天与校验文件")
    p("chat.py 启动官方 tcp_eth_udp 子进程，将应用消息写入其标准输入，并从标准输出接收对方数据。应用字节实际经过自己的 ByteStream、TCP、NetworkInterface 与 Router；Python 没有改用系统 TCP 建立另一条数据连接。")
    p("应用用一行 JSON 定义一条消息，支持 UTF-8 聊天。文件通过 file-start、Base64 分块、file-end 三种消息传送；接收方逐块计算 SHA-256，核对字节数后才发布文件。")
    story.append(Paragraph("if (state['received'] != state['size'] or<br/>"
                           "&nbsp;&nbsp;&nbsp;state['hash'].hexdigest() != state['sha256']):<br/>"
                           "&nbsp;&nbsp;&nbsp;raise ValueError('file length or SHA-256 mismatch')", mono))
    markdown.append("```python\nif (state['received'] != state['size'] or\n    state['hash'].hexdigest() != state['sha256']):\n    raise ValueError('file length or SHA-256 mismatch')\n```\n")
    p("最多 16 MiB/文件、4 个在途文件，限制单行长度；拒绝路径穿越，使用独立 .part 临时文件，验证后发布且不覆盖已有文件。8 项协议检查覆盖二进制、空文件、中文、损坏、路径和大小边界。")
    p("本机聊天室两个方向均收到 Hello 消息，并各接收 1 MiB 文件，收据、实际文件和哈希一致。接收文件原始内容留在 build/check7-chat-final，提交的证据保留聊天日志、收据、哈希和首部抓帧。")
    story.append(PageBreak())
    h("6. 已定位的整合问题")
    table(["问题", "修正与验证"], [
        ["GCC 13 范围遍历诊断", "fun_router 使用 args.subspan(1)，保留跳过程序名的行为。"],
        ["默认 Address 的 UBSan 诊断", "空地址长度为零时跳过 memcpy，避免向库函数传空源指针。初次失败日志保留在 tiny。"],
        ["应用层静态检查", "Route 字段显式默认初始化。没有改变 Point 6 的选路规则。"],
    ], [150, 325])
    p("最终完整 CTest 40/40 通过；项目源文件、改动的 fun_router 与 address 静态检查通过，格式检查通过。Windows UDP 转发脚本在一台 Windows 回环中通过双向字节、未知来源过滤、空闲超时继续运行共 4 项检查。")
    h("三机联调中解决的问题")
    table(["实际现象", "处理与结果"], [
        ["A 的转发目标端口写成 1908", "改为 19080；保留原始 READY 与修正记录。"],
        ["A 的来源被 NAT 改成 Wi-Fi IP 与临时端口", "Ubuntu 改连宿主机 VMnet8 192.168.226.1；不扩大转发来源过滤，随后三次往返通过。"],
        ["B 下载脚本等待、文件未签名", "直接传文件；对该文件使用 Unblock-File，未改全局执行策略。"],
        ["同学机器克隆失败", "发离线源码与已编译端点包，校验 ZIP/文件哈希、权限及 Ubuntu 启动；两位在 Ubuntu 主目录运行。"],
    ], [150, 325])
    physical_drawing = Drawing(490, 120)
    for x1, x2 in [(122, 186), (296, 360)]:
        physical_drawing.add(Line(x1, 69, x2, 69, strokeColor=colors.HexColor("#6487a3")))
    for x, label, virtual, physical in [
        (12, "同学 A / 客户端", "80.6.5.4", "Windows 10.200.54.254"),
        (186, "本机用户 / 路由器", "80.0.0.1 / 50.0.0.1", "Windows 10.200.49.154"),
        (360, "同学 B / 服务端", "50.9.8.7:80", "Windows 10.200.93.187"),
    ]:
        physical_drawing.add(Rect(x, 42, 110, 54, fillColor=colors.HexColor("#e5eef5"),
                                  strokeColor=colors.HexColor("#174b70")))
        physical_drawing.add(String(x + 55, 76, label, fontName="CJK", fontSize=9, textAnchor="middle"))
        physical_drawing.add(String(x + 55, 57, virtual, fontName="Helvetica", fontSize=8, textAnchor="middle"))
        physical_drawing.add(String(x + 55, 23, physical, fontName="Helvetica", fontSize=8, textAnchor="middle"))
    story.append(physical_drawing)
    markdown.append("```text\nA (80.6.5.4) -- Router (80.0.0.1 / 50.0.0.1) -- B (50.9.8.7:80)\nWindows 10.200.54.254 -- Windows 10.200.49.154 -- Windows 10.200.93.187\n```\n")
    story.append(PageBreak())
    h("7. 三台电脑实测" if peer_result else "7. 三机实验：配置完成，结果待验证")
    peer_rows = []
    for key, role in [("router", "本机路由器"), ("client_A", "同学 A 客户端"), ("server_B", "同学 B 服务端")]:
        node = peer_config[key]
        kind = "虚拟机" if node["kind"] == "VM" else node["kind"]
        peer_rows.append([role, node["windows"], node["ubuntu"] + " / " + kind])
    table(["角色", "Windows 地址", "Ubuntu 内部地址"], peer_rows, [115, 150, 210])
    p("以上为真实外层地址。A 的 VMnet8 为 192.168.226.1，B 为 192.168.105.1；本机 WSL 使用 Windows 侧 172.18.80.1。所有程序使用同一份项目实现，参与者用 A、B 和本机用户代称，不声称三人独立协议栈互操作。未提供姓名或 SUNet ID，未虚构。")
    table(["位置", "本地 UDP", "物理发送目标"], [
        ["A Ubuntu 端点", "2080", "192.168.226.1:12080（自己的 Windows）"],
        ["A Windows 转发", "12080", "本机路由器 Windows 10.200.49.154:19080"],
        ["本机 Windows 两侧转发", "19080 / 19050", "WSL 172.18.80.5:9080 / :9050，另一端为 A/B Windows"],
        ["B Windows 转发", "12050", "本机路由器 Windows 10.200.49.154:19050"],
        ["B Ubuntu 端点", "2050", "由首个收到的帧学习本机 Windows 应答地址"],
    ], [135, 80, 260])
    p("内层拓扑为 A(80.6.5.4) - 路由器(80.0.0.1 / 50.0.0.1) - B(50.9.8.7:80)。路由器将 80/8 直连到 ucla 接口，50/8 直连到 stanford 接口。外层 Windows 转发只搬运 UDP，不替代中间 C++ 路由器的 IP 选路。")
    if peer_result:
        p("A 和 B 的 UDP 预检各 3/3 通过，控制台回传与本机应答日志相互吻合。正式路由器随后记录两个方向的 TCP 数据。两份接收端 FILE VERIFIED 均为 1,048,576 字节，SHA-256 与确定生成的原文件一致：")
        story.append(Paragraph(peer_result["expected_sha256"], mono))
        markdown.append("```text\n" + peer_result["expected_sha256"] + "\n```\n")
        for index, item in enumerate(peer_result["received_file_verifications"], 1):
            p("接收记录 " + str(index) + "：" + item["saved_as"])
        p("两份原始控制台片段未单独标注 A/B，证据文件保留原顺序，没有强行给文件名分配方向；路由器双向数据记录与用户按两个端点回传的结果共同支持双向传输结论。记录分为用户回传和本机直接采集两类，不将回传写成远程自动读取。")
        p("本次没有从缺少完整载荷的日志推算文件哈希，也不把日志中含 ACK、首部和重传的字节和当成有效吞吐。三路由器和并发多连接实验仍属于前述本机拓扑，三台电脑实际使用的是一个路由器、两个端点。")
    else:
        p("实际跨机聊天、双向文件及收据尚待核对，当前配置不作为已完成三人联网的证明。")
    p("当前三机配置、实际错误与验证顺序见 writeups/check7-session-2026-11-25.md；旧 11 月 24 日地址已标注不可复用。")
    h("8. 体会、复现与来源")
    p("从模块检查走到进程间实跑，主要学习点是区分两层 IP 地址、理解选路与 ARP 的分工，以及保留可检查的文件与报文证据。后续可加入拥塞控制和实时应用，比较吞吐、时延与丢包恢复之间的取舍；本次未开展这些测量。")
    p("源码、验证与本文由 Codex 按用户要求辅助完成，未虚构独立完成或到课情况。实验数据只取自保存的 JSON、日志、收据和 pcap，拓扑图对应实际启动配置。")
    p("复现：tools/check7/lab.py --sanitized --output 新目录；更大拓扑加 --topology bigger，定点丢包加 --drop-first-data，聊天室加 --chat。先按 tools/check7/README.md 构建。")
    p("来源：CS144 官方 Checkpoint 7 指导书：https://cs144.github.io/assignments/check7.pdf；本地官方应用 apps/tcp_eth_udp.cc、apps/fun_router.cc；原始实验记录 writeups/check7-data。")
    markdown.append("\n学习入口：[源码新手讲解](check7-source-code-guide.md) · [三机启动说明](check7-peer-setup.md) · [验证摘要](check7-screenshots/validation.txt)\n")
    shots = [ROOT / "writeups/check7-screenshots/01-chat-send.jpg", ROOT / "writeups/check7-screenshots/02-chat-receive.jpg"]
    if all(path.is_file() for path in shots):
        markdown.append("实际代码截图：[文件发送](check7-screenshots/01-chat-send.jpg) · [校验发布](check7-screenshots/02-chat-receive.jpg)\n")
    else:
        markdown.append("实际桌面代码截图尚待补齐。\n")
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")

    def page_number(canvas, doc):
        canvas.setFont("CJK", 8)
        canvas.setFillColor(colors.HexColor("#526779"))
        canvas.drawString(18 * mm, 12 * mm, "CS144 / Point 7 / 本机与三机实测已验证" if peer_result else "CS144 / Point 7 / 本机已验证 · 三机待验证")
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, str(doc.page))

    SimpleDocTemplate(str(args.pdf), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                      topMargin=17 * mm, bottomMargin=20 * mm,
                      title="Checkpoint 7 全栈网络与迷你聊天室", author="项目实验记录 / Codex 辅助").build(
                          story, onFirstPage=page_number, onLaterPages=page_number)
    print(args.pdf)


if __name__ == "__main__":
    main()
