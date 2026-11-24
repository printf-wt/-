# 从环境配置到 Checkpoint 0、1 和 2

本文面向计算机网络新手，按照本项目实际开发过程，说明环境怎样配置、
各阶段实验分别解决什么问题、代码怎样验证，以及最后怎样提交到 GitHub。
命令会标明运行位置，阅读时先分清 Windows PowerShell 和 Ubuntu 终端。

记录日期：2026 年 11 月 24 日。

## 1 各阶段实验完成了什么

| 阶段 | 本次编写的模块 | 作用 |
|---|---|---|
| Checkpoint 0 | webget | 连接服务器、发送 HTTP 请求、读取并输出响应 |
| Checkpoint 0 | ByteStream | 在有限容量的内存缓冲区中，按顺序写入和读取字节 |
| Checkpoint 1 | Reassembler | 整理带索引的乱序、重复、重叠子串，交付连续字节 |
| Checkpoint 2 | Wrap32 | 在 32 位 TCP 序号和内部 64 位绝对序号之间换算 |
| Checkpoint 2 | TCPReceiver | 处理收到的 TCP 消息，生成确认号、接收窗口和复位标志 |

webget 目前使用 Linux 自带的 TCP。ByteStream 和 Reassembler 是我们
实现的基础模块；Checkpoint 2 已将它们接入自己的 TCP 接收端。
TCP 发送端与完整实网互操作安排在后续阶段。
本次已经完成编程和自动化验证，手工联机、SMTP 会话和抓包部分尚未执行。

“Checkpoint 0/1/2”是实验阶段名称；命令中的 `check0`、`check1`、`check2` 则是
工程为这些阶段提供的构建与自动检查任务。

## 2 先认识开发环境

| 名称 | 负责什么 |
|---|---|
| Windows | 日常桌面、文件管理和编辑器运行环境 |
| WSL2 | 让 Windows 运行 Linux 环境 |
| Ubuntu | 本项目实际进行编译和测试的 Linux 系统 |
| Visual Studio / VS Code | 打开、阅读和编辑源码 |
| g++ | 将 C++ 源码编译成程序 |
| CMake | 读取工程配置，组织源码、库和测试之间的构建关系 |
| make | 按生成的构建规则执行编译任务 |
| clang-format | 统一代码缩进、空格等格式 |
| clang-tidy | 静态分析源码，发现潜在问题和不合理写法 |
| Git | 保存修改历史，获取框架，并把提交同步到 GitHub |

工作方式是：在 Windows 编辑同一份源码，在 Ubuntu 编译和运行。
实验使用 Linux 网络接口和脚本，因此运行结果以 Ubuntu 中的构建、测试为准。
Windows 编辑器中的提示还取决于编辑器自己的编译器与头文件配置。

## 3 检查 WSL 与 Ubuntu

开始工作时，这台电脑已经装有 WSL2 和 Ubuntu，我没有重新安装它们。

在 **Windows PowerShell** 中查看已有环境：

```powershell
wsl --list --verbose
```

当时能看到名为 Ubuntu 的环境，其 WSL 版本为 2。
进入它使用下面的命令：

```powershell
wsl -d Ubuntu
```

进入后，输入的就是 Linux 命令。要退出 Ubuntu、返回原来的 PowerShell，
可以输入 `exit`。

## 4 检查并安装开发工具

在 **Ubuntu 终端** 中检查系统和工具：

```bash
cat /etc/os-release
g++ --version
cmake --version
```

刚开始 Ubuntu 中缺少 g++、CMake 等开发工具，所以我补齐了它们。
实际安装通过 WSL 管理员账户完成；普通用户手动复现时，可使用等价的 sudo 命令：

```bash
sudo apt-get update
sudo apt-get install -y g++ make cmake clang-format clang-tidy-20
```

`sudo` 表示使用 Linux 管理员权限；`apt-get update` 更新可安装软件的目录；
`apt-get install` 安装指定软件；`-y` 表示自动确认安装。
make 等构建工具也在这次环境配置中补齐。
当前电脑已完成安装，下面的版本信息用于核对，无需重复安装。

| 工具或系统 | 本次核对的版本 |
|---|---|
| Ubuntu | 24.04.4 LTS |
| g++ | 13.3.0 |
| CMake | 3.28.3 |
| clang-format | 18.1.3 |
| clang-tidy | 20.1.2 |

仓库要求 C++23 标准，CMake 最低版本为 3.24.2。
C++23 是语言标准编号，g++ 13.3 是编译器版本，两者含义不同。
这些要求分别写在 [编译配置](../etc/cflags.cmake) 和
[主构建文件](../CMakeLists.txt) 中。

## 5 找到工程并理解目录

你已把官方仓库 fork 到自己的账号，并把代码克隆到本地。
Windows 和 Ubuntu 对同一份文件使用不同的路径写法：

| 环境 | 项目路径 |
|---|---|
| Windows | `D:\计算机网络\课程设计\-` |
| Ubuntu | `/mnt/d/计算机网络/课程设计/-` |

其中 `/mnt/d/` 对应 Windows 的 D 盘。
在 **Ubuntu 终端** 中进入工程：

```bash
cd "/mnt/d/计算机网络/课程设计/-"
pwd
ls
```

`cd` 切换目录，`pwd` 显示当前位置，`ls` 列出当前文件。
这里文件夹的名字是单个 `-`。在 Linux 中，单独的 `cd -` 表示返回上一个目录，
所以应使用上面的绝对路径，或在父目录执行 `cd ./-`。

| 路径 | 内容 |
|---|---|
| apps/ | 网页获取等应用程序 |
| src/ | 字节流、重组器等实验实现 |
| util/ | 已提供的套接字、文件描述符等基础设施 |
| tests/ | 官方测试与性能基准 |
| writeups/ | 实验记录、报告、代码截图和测试日志 |
| CMakeLists.txt | 描述工程怎样组织和编译 |
| build/wsl/ | 本机 Linux 编译产物，已被 Git 忽略 |

`.hh` 主要声明类、成员和函数接口；`.cc` 填写这些功能的具体实现。
刚克隆下来的框架中，许多函数只有 `Your code here` 或未实现提示。

## 6 配置和启动构建

下面的命令都在 **Ubuntu 的项目根目录** 中运行：

```bash
cmake -S . -B build/wsl
```

| 参数 | 含义 |
|---|---|
| `-S .` | 源码位于当前目录，`.` 表示当前目录 |
| `-B build/wsl` | 将构建配置和产物放进 build/wsl |

CMake 会检查编译器，读取工程配置，并生成后续编译所需的规则。
配置成功后，可以编译并执行指定阶段的检查：

```bash
cmake --build build/wsl --target check0
cmake --build build/wsl --target check1
cmake --build build/wsl --target check2
```

实际开发时，我还使用了下面的形式，限制并行构建任务数为 4：

```bash
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check1
```

配置成功说明编译规则已经准备好；编译成功说明代码能生成程序；
测试通过才说明程序在相应测试输入下得到正确结果。

### 当时遇到的换行符问题

首次启动构建时，虽然脚本存在，仍报了 `No such file or directory`。
原因是 Windows 的 CRLF 换行影响了 Linux 对脚本解释器的识别。
我将本地 shell 脚本处理为 LF 换行，并添加了
[.gitattributes](../.gitattributes)：

```gitattributes
*.sh text eol=lf
```

它要求 Git 检出 `.sh` 脚本时使用 LF 换行。
[.gitignore](../.gitignore) 还增加了 `.vs/` 和 `out/`，
避免把 Visual Studio 的本地生成文件提交到仓库。

## 7 Checkpoint 0 的网页获取程序

修改文件：[apps/webget.cc](../apps/webget.cc)。

目标是实现一个简单的 HTTP 客户端：

```text
连接服务器 → 发送 HTTP 请求 → 循环读取响应 → 输出完整内容
```

比如访问 `/hello`，请求的文字内容是：

```http
GET /hello HTTP/1.1
Host: cs144.keithw.org
Connection: close

```

实际发送时，每行以 `\r\n` 结束，并以额外的空行结束请求头。
`GET` 表示获取资源；`Host` 说明目标网站；`Connection: close`
请求服务器在响应结束后关闭连接。

我补上的步骤如下：

1. 创建框架提供的 TCPSocket，作为网络通信的入口。
2. 用 Address 解析目标主机与 HTTP 服务，并建立连接。
3. 使用 write_all 发送完整请求。
4. 循环调用 read，把每次读到的内容输出。
5. 读到 EOF 后结束并关闭套接字。

一次 read 不保证得到整个网页，网络响应可能分多次到达。
这里的 EOF 表示对方已结束发送；循环读取是保证内容完整的关键。
程序会输出服务器的 HTTP 响应头及正文，TCP 传输由 Linux 内核提供。

编译好后，可在 **Ubuntu 项目根目录** 中亲手运行：

```bash
./build/wsl/apps/webget cs144.keithw.org /hello
```

自动化验证实际使用的是 tests/webget_t.sh 中的远端请求与预期结果。

## 8 Checkpoint 0 的内存字节流

修改文件：[src/byte_stream.hh](../src/byte_stream.hh) 和
[src/byte_stream.cc](../src/byte_stream.cc)。

ByteStream 是一个有容量限制的数据缓冲区。一端写入，另一端按顺序读取：

```text
Writer 写入 → ByteStream 暂存 → Reader 读取
```

假设容量为 5，且写入方遵守接口约定：

| 操作 | 当前缓冲内容 | 剩余容量 |
|---|---|---:|
| push("abcdef") | abcde，多出的 f 不被接收 | 0 |
| pop(2)，移除已读取的 ab | cde | 2 |
| push("fg") | cdefg | 0 |
| close() | cdefg，仍然可以读取 | 0 |
| 读完并 pop 剩余 5 字节 | 空，读取结束 | 5 |

容量限制的是某一时刻暂存的字节数，不是整个流的总长度。
读取方持续消费并腾出空间后，小缓冲区也能承载很长的数据流。
push 的返回类型是 void，调用方通过容量和累计写入量等接口判断接收情况。

| 接口 | 本次实现的行为 |
|---|---|
| push(data) | 只接收剩余容量允许的部分；关闭后不再接收 |
| peek() | 返回下一段可读数据的视图，不移除数据 |
| pop(len) | 移除相应数量的已读取字节 |
| close() | 标记写入结束 |
| available_capacity() | 查询剩余可写容量 |
| bytes_pushed()/bytes_popped() | 查询累计写入量与累计移除量 |
| bytes_buffered() | 查询已写入但尚未移除的数据量 |
| is_finished() | 仅当已经关闭且缓冲区为空时返回 true |

内部采用字符串分块队列，用队首偏移标记当前读到哪里。
读完一块再释放它，避免每次 pop 都整体搬移剩余数据。
peek 可以只返回队首块中未读的部分，不保证一次返回全部缓冲内容。

“关闭”和“读完”是两个不同状态：close 后如果还有缓冲数据，
is_finished 仍然是 false，直到这些数据也被读完。

![ByteStream 写入端代码](check0-screenshots/01-byte-stream-writer.jpg)

其余代码截图见 [Checkpoint 0 截图目录](check0-screenshots/)。

## 9 获取 Checkpoint 1 框架

Checkpoint 0 完成后，本地还缺少重组器接口、实现模板和专项测试。
我添加官方远程仓库，并获取 check1-startercode：

```bash
git remote add upstream https://github.com/CS144/imp.git
git fetch upstream check1-startercode
git merge --no-commit --no-ff upstream/check1-startercode
```

这些是当时执行的接入步骤，当前工程已经完成合并。
remote add 只需配置一次；现在可通过 `git remote -v` 查看已有设置。
--no-commit 让合并先停下来供检查和继续实现，--no-ff 保留合并记录。

| 远程名称 | 指向哪里 | 用途 |
|---|---|---|
| origin | printf-wt/- | 上传自己的成果 |
| upstream | CS144/imp | 获取官方后续实验框架 |

本次合入的官方提交是 5f35eb9，增加了 Reassembler、七组功能测试、
性能基准、测试驱动与报告模板。已有 ByteStream 和 webget 实现得以保留。

## 10 Checkpoint 1 的乱序重组器

修改文件：[src/reassembler.hh](../src/reassembler.hh) 和
[src/reassembler.cc](../src/reassembler.cc)。

网络传来的数据可能乱序、重复，或与已有数据部分重叠。
Reassembler 根据每段数据的流索引，把它们恢复成连续的字节流。
索引从 0 开始，例如：

```text
原始内容：A B C D E F
流索引：  0 1 2 3 4 5
```

假设容量为 8，应用暂时还没有读取数据：

| 到达的片段 | ByteStream 中的内容 | 重组器暂存内容 |
|---|---|---|
| first_index=3，data="DEF" | 空 | 索引 3 到 5 的 DEF |
| first_index=0，data="AB" | AB | 索引 3 到 5 的 DEF |
| first_index=2，data="CD" | ABCDEF | 空 |

最后一次的 D 已经存在，所以只需保存新收到的 C；空洞补齐后，
即可交付 C 和之前保存的 DEF。不会重复交付 D。

如果第一段 DEF 带有 is_last_substring=true，它表示原始流到这里结束，
不是说这段必须最后到达。重组器先记住结束索引 6，等 ABCDEF 全部连续
交付后再关闭 ByteStream；应用把这 6 字节读完后才到达读取结束状态。

我实现的顺序是：

1. 检查输出是否已关闭，记录结束位置，并防止索引加法溢出。
2. 由已交付位置和下游剩余容量确定接收窗口，裁掉窗口外的数据。
3. 在按索引排序的 map 中查找已有区间，仅保存尚未收到的字节。
4. 如果能保存整个输入子串，就使用移动语义，减少复制。
5. 从最早区间开始，把所有连续数据立即写入 ByteStream。
6. 到达结束位置后关闭输出；待重组字节数由各暂存区间长度累计得到。

容量还要同时考虑“已经重组但未被应用读取”的数据。
窗口右边界等价于“已读出字节数 + 总容量”；不能直接用已交付位置加总容量，
否则会忽略 ByteStream 中尚未读取的数据。

两个模块的关系如下：

```text
带索引的乱序子串 → Reassembler 整理 → ByteStream 暂存 → 应用按顺序读取
```

![Reassembler 去重与连续交付代码](check1-screenshots/02-deduplication-and-delivery.jpg)

## 11 Checkpoint 2 的序号换算与 TCP 接收端

### 11.1 为什么还要做接收端

Checkpoint 1 的重组器能够整理数据，但它接收的是“流索引 + 子串”。
真实 TCP 消息携带的却是报文序号、开始标志、结束标志和载荷。
本阶段需要在这两种表示之间衔接，并告诉对方“还缺哪个位置、还能接收多少”。

```text
TCP 消息：seqno、SYN、payload、FIN、RST
                    ↓
TCPReceiver：识别标志，换算数据位置
                    ↓
Reassembler：整理乱序、重复与重叠片段
                    ↓
ByteStream：暂存连续数据，交给应用读取
```

先认识消息中的几个字段：

| 字段 | 可以怎样理解 |
|---|---|
| seqno | 这条消息开头的序号 |
| SYN | 字节流的开始标志，携带初始序号 ISN |
| payload | 真正要交给应用的数据字节 |
| FIN | 字节流的结束标志 |
| RST | 发生错误，要求复位连接的标志 |

TCPReceiver 的 send() 负责生成确认信息对象，实际封装和网络发送由框架上层负责。

### 11.2 当时怎样获取框架

沿用前面已经配置好的 upstream，我在本地工程中执行：

```bash
git fetch upstream check2-startercode
git merge --no-commit --no-ff upstream/check2-startercode
```

这是本次开发时的合入步骤，当前 main 已经包含这些修改。
框架提交是 d4aea19a311753ac47bd074cb1c5bf778191962b，带来了：

- wrapping_integers.hh/.cc：32 位序号包装类型及待实现的换算函数。
- tcp_receiver.hh/.cc：TCP 接收端接口及待实现的处理函数。
- 五组序号测试、七组接收端测试，以及报文结构与适配基础设施。
- 与新报文类型配套的编译开关和 Checkpoint 2 报告模板。

已有字节流和重组器继续使用，官方 tests、util、etc 内容保持合入后的原样。

### 11.3 先分清三种编号

TCP 报文的序号只有 32 位，从 0 数到 4294967295 后会重新回到 0。
而且每条流从一个初始序号 ISN 开始，不固定从 0 开始。

为了便于内部计算，我们还使用从 0 开始的 64 位绝对序号。
Reassembler 使用的流索引则只给数据字节编号，不给 SYN、FIN 编号。

例如，设 ISN=100，原始内容是 ABCDEF：

| 元素 | SYN | A | B | C | D | E | F | FIN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TCP 序号 | 100 | 101 | 102 | 103 | 104 | 105 | 106 | 107 |
| 绝对序号 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| 流索引 | 无 | 0 | 1 | 2 | 3 | 4 | 5 | 无 |

这里最重要的是：SYN 和 FIN 各占一个序号位置，但不属于应用的数据。
因此普通数据的流索引等于其绝对序号减 1。

### 11.4 实现 wrap 和 unwrap

阅读文件：[wrapping_integers.hh](../src/wrapping_integers.hh)、
[wrapping_integers.cc](../src/wrapping_integers.cc)。

wrap 的方向是“绝对序号 → TCP 序号”：

```text
TCP 序号 = (ISN + 绝对序号) 对 2^32 取余
```

“取余”就是保留除法的余数，保证结果落在 32 位范围内。
例如 ISN=4294967294，绝对序号为 3，相加后越过最大值，最后得到序号 1。
实现中通过转换为 32 位无符号数并相加，完成这种回绕。

unwrap 的方向是“TCP 序号 → 绝对序号”，但它还需要一个 checkpoint。
这个 checkpoint 是当前大致走到的位置，用于判断已经绕了几圈。

例如 ISN=100，收到序号 105，它可能对应绝对序号 5，也可能对应 2^32+5：

| checkpoint 靠近哪里 | 应还原出的绝对序号 |
|---|---:|
| 3 | 5 |
| 4294967299，即 2^32+3 | 4294967301，即 2^32+5 |

我的实现先构造当前周期中的候选，再比较相邻周期，选择最近的合法值。
调整周期前检查 64 位上下界，避免下溢或上溢；距离相同时选择较小候选。

![序号换算的实际代码](check2-screenshots/01-wrapping-integers.jpg)

### 11.5 实现 receive 接收逻辑

阅读文件：[tcp_receiver.hh](../src/tcp_receiver.hh)、
[tcp_receiver.cc](../src/tcp_receiver.cc)。

我只额外保存一个可选的 isn_ 状态，用于区分“还没收到 SYN”和“已知初始序号”。
其余进度、关闭和错误状态从重组器或字节流查询。

receive 的处理步骤如下：

1. 收到 RST 时，将字节流标记为错误；已处于错误状态时停止继续接收。
2. 第一次收到 SYN 时记录 ISN。还不知道 ISN 的普通数据暂不接收。
3. 以“已连续交付字节数 + 1”为 checkpoint，将 TCP 序号还原为绝对序号。
4. 排除把 SYN 的位置当作普通数据的无效消息，避免错误地减出极大流索引。
5. 根据是否携带 SYN，换算载荷首字节的流索引。
6. 把流索引、载荷和 FIN 标志交给 Reassembler。

例如，普通数据的绝对序号为 4，说明其流索引为 3，应从原始内容的 D 开始。
如果 SYN 和数据在同一条消息中到达，则先跨过 SYN 的位置，再交付数据。
重复到达同一个 SYN 时，已经收到的数据和已记录的 ISN 都不会被重新初始化。

接收端认识 TCP 的标志和编号；乱序、重叠、去重、容量裁剪仍由重组器完成。
这样可以直接复用前一个实验的实现和验证结果。

### 11.6 实现确认号和接收窗口

send() 返回三个字段：

| 字段 | 表达的意思 |
|---|---|
| ackno | 接下来期待的 TCP 序号 |
| window_size | 从确认位置开始还愿意接收的序号范围宽度 |
| RST | 当前字节流是否已经发生错误 |

确认号需要以“连续收齐”为依据。收到后面的片段，但前面仍有空洞时，
确认号应停在第一个缺失的位置。

收到 SYN 后，先计算绝对确认位置：

```text
绝对确认位置 = 已连续交付的数据字节数 + 1（SYN）
             + 1（仅当完整重组到结束位置、需要确认 FIN 时）
```

再通过 wrap 转回 32 位序号。收到 SYN 前，确认号为空。
确认 FIN 使用 Writer 是否关闭来判断；应用暂时还没读完缓冲数据，不影响确认 FIN。

窗口来自 ByteStream 的当前可用容量，并限制到 16 位字段最大值 65535。
缓冲区满时窗口为 0，应用读取并腾出空间后窗口增大。
乱序数据已经位于当前接收序号范围内，不再从窗口宽度中重复扣减。

![确认号与窗口的实际代码](check2-screenshots/03-receiver-ack-window.jpg)

### 11.7 把三个模块串起来推演

继续设 ISN=100、内容为 ABCDEF、容量为 8。假设应用最初还没有读取：

| 收到的消息或发生的操作 | 连续交付进度 | ackno | 窗口 |
|---|---|---:|---:|
| 刚创建接收端 | 空 | 无 | 8 |
| SYN，seqno=100 | 空 | 101 | 8 |
| DEF+FIN，seqno=104 | 前面有空洞，DEF 暂存 | 101 | 8 |
| AB，seqno=101 | AB 已交付 | 103 | 6 |
| CD，seqno=103 | ABCDEF 全部交付并确认 FIN | 108 | 2 |
| 应用读取全部 6 字节 | 数据已读出 | 108 | 8 |

可以重点观察三个地方：

- DEF+FIN 先到时，确认号仍然是 101，因为还缺 A 开始的数据。
- CD 到达后，C 补齐空洞，D 与已有片段重复，最终连续交付 ABCDEF。
- ACK=108 计入了 SYN、六个数据字节和 FIN；应用读取后，ACK 不变而窗口恢复。

### 11.8 怎样编译和验证本阶段

在 Ubuntu 的项目根目录执行：

```bash
cmake -S . -B build/wsl
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check2
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check0
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target tidy
clang-format --dry-run --Werror src/wrapping_integers.hh src/wrapping_integers.cc src/tcp_receiver.hh src/tcp_receiver.cc
python3 writeups/check2-screenshots/boundary-validation.py
```

check2 的 30 项官方检查通过，覆盖旧模块、序号换算、接收端和已有性能基准。
check0 的 11 项回归检查通过，包含远端 HTTP 请求。
补充脚本在临时目录编译实际 Wrap32 实现，运行 10 项 64 位边界检查，
覆盖最大值、非零 ISN、相邻周期和等距候选，也全部通过。

30 项官方检查与 10 项补充检查是两组不同记录，后者没有改动官方测试。
全部 src 实现通过静态分析，本阶段四个源码文件通过格式检查。

阅读代码时，建议先看 wrap，再看 unwrap，然后沿 receive 到 Reassembler 的调用阅读，
最后对照上面的表格，手工算出每次 send() 的确认号和窗口。
更多细节见 [Checkpoint 2 实现报告](check2.md)。

## 12 怎样判断代码正确

官方测试会自动构造输入，并核对输出、容量、结束状态和性能。
测试结果中的一项可能是构建或基准任务，不等于一个单独的网络功能。

| 测试内容 | 要验证的问题 |
|---|---|
| 容量已满 | 是否拒绝继续占用缓冲空间 |
| 数据乱序 | 是否暂存后到的数据并等待空洞补齐 |
| 数据重复或重叠 | 是否只保存和输出一份字节 |
| 提前收到末段 | 是否在连续数据尚未到齐时继续等待 |
| 应用读取数据 | 接收窗口是否随着可用空间增加而移动 |
| 极大索引 | 是否避免索引回绕后错误接收数据 |
| 性能基准 | 是否达到实验要求的吞吐 |

本次记录的验证结果：

- Checkpoint 0 初次实现后，11 项检查全部通过。
- Checkpoint 1 实现后，18 项检查全部通过，其中也包含 ByteStream 回归检查。
- 合入 Checkpoint 1 后，再运行 Checkpoint 0，其 11 项检查也全部通过。
- Checkpoint 2 的 30 项官方检查通过，包含前两阶段的模块回归。
- 合入 Checkpoint 2 后，另跑 Checkpoint 0 的 11 项检查通过，补充边界检查 10 项通过。
- 编译中的 ASan 检查常见内存访问错误，UBSan 检查未定义行为。
- 静态检查曾提示重组器有不必要的数据复制，我增加整块移动处理后重新验证通过。
- 最终通过相关静态分析与格式检查，官方测试内容保持原样。

“回归检查”表示新增功能后，再检查以前的功能是否仍然正常。
check1 本身不包含远端 HTTP 请求，因此另跑 check0 有明确作用。
check2 同样不包含远端 HTTP 请求，所以本阶段也另跑 check0。

原始记录：

- [Checkpoint 0 验证摘要](check0-screenshots/validation.txt)
- [Checkpoint 1 验证摘要](check1-screenshots/validation.txt)
- [Checkpoint 1 完整测试日志](check1-screenshots/check1-ctest.log)
- [Checkpoint 0 回归日志](check1-screenshots/check0-regression.log)
- [Checkpoint 1 实现报告](check1.md)
- [Checkpoint 2 验证摘要](check2-screenshots/validation.txt)
- [Checkpoint 2 完整测试日志](check2-screenshots/check2-ctest.log)
- [Checkpoint 2 的 HTTP 回归日志](check2-screenshots/check0-regression.log)
- [Checkpoint 2 补充边界检查](check2-screenshots/boundary-validation.log)
- [Checkpoint 2 实现报告](check2.md)

重组器官方基准的输出使用了不同于实际输入字节数的计算分子。
报告中同时保留原始输出和折算后的有效载荷吞吐，避免混淆两种口径。

## 13 截图、提交与推送

功能验证后，我在 Windows 编辑器中打开主要代码并保存实际截图，
再把源码、报告、截图和测试日志一起纳入 Git。

| 操作 | 含义 |
|---|---|
| Fork | 在 GitHub 上把官方仓库复制到自己的账号 |
| Clone | 把远程仓库下载为本地工程 |
| Fetch | 下载远程的新提交和分支信息 |
| Merge | 将指定分支的修改合入当前分支 |
| Add | 选择本次准备提交的文件，即放入暂存区 |
| Commit | 在本地建立一条带说明的修改记录 |
| Push | 将本地提交上传到远程仓库 |

本次 Git 操作使用 Windows 已有的 Git 与 SSH 认证，
Ubuntu 中的开发工具负责编译和测试。
本地保存文件不会自动更新 GitHub，需要先 commit 再 push。

一次提交的流程是：

1. 用 git status 检查本地修改。
2. 用 git add 明确选择本次要提交的文件。
3. 用 git diff --cached 检查暂存内容。
4. 写清提交标题、文件改动、设计意图和实际验证结果，再执行 git commit。
5. 执行 git push origin main。
6. 比较本地与远端提交，并确认工作区干净。

现在可以查看真实记录：

```bash
git status
git remote -v
git log -1 --format=full
```

## 14 可以亲手复现的最短流程

工具和框架已经配置完成。先在 **Windows PowerShell** 中进入 Ubuntu：

```powershell
wsl -d Ubuntu
```

然后在 **Ubuntu 终端** 中依次执行：

```bash
cd "/mnt/d/计算机网络/课程设计/-"
pwd
g++ --version
cmake --version
cmake -S . -B build/wsl
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check0
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check1
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check2
```

先观察每条命令的输出，再读源码。建议顺序为：webget.cc、byte_stream.hh、
byte_stream.cc、reassembler.hh、reassembler.cc、wrapping_integers.hh/.cc、
tcp_receiver.hh/.cc，最后阅读 tests 中的测试。

学习时可分别观察三个阶段的输出；日常验收时，check2 已覆盖旧模块的回归，
配合 check0 检查 HTTP 即可，不必每次重复运行 check1。

阅读 ByteStream 时，尝试手工计算每次 push/pop 后的剩余容量；
阅读 Reassembler 时，按前面的 ABCDEF 示例画出暂存区间和已交付位置。
阅读 TCPReceiver 时，再加入 SYN、FIN 的序号占用，逐步算出 ACK=101、103、108。

## 15 阶段完成记录

| 提交 | 内容 |
|---|---|
| [c0e5235](https://github.com/printf-wt/-/commit/c0e5235847d6c1ca3eccf1082f93e50b50885dc9) | 完成 Checkpoint 0 的 HTTP 客户端、字节流、截图及验证记录 |
| [2979d12](https://github.com/printf-wt/-/commit/2979d12740c91fc858f2920ca12abc1daae57395) | 合入 Checkpoint 1 框架，完成重组器、报告、截图和测试记录 |
| [5a2442f](https://github.com/printf-wt/-/commit/5a2442f1dc172788c396d2e2d054342284d2f4f8) | 合入 Checkpoint 2 框架，完成序号换算、TCP 接收端及验证记录 |

实现、验证与本文整理由 Codex 按用户请求辅助完成。
