# Checkpoint 1 乱序字节流重组器

本次完成重组器的编程实现、自动化验证与主要代码截图。
手工网络互通与抓包部分尚未执行，本文不作为该部分的完成记录。

## 框架与环境

框架来自 CS144/imp 的 check1-startercode 分支，提交 5f35eb9。
合入官方接口、七组重组器功能测试、性能基准及报告模板。
延续 Checkpoint 0 的 ByteStream，保持所有公开接口不变。
环境为 Ubuntu 24.04.4 LTS / WSL2、g++ 13.3、CMake 3.28.3，
静态检查使用 clang-tidy-20。

## 程序结构与设计

使用 map<uint64_t, string> 按索引保存互不重叠的待重组区间，
用 optional<uint64_t> 记录流的结束位置。一次 insert 按以下顺序处理：

1. 检查输出是否已经关闭；记录结束位置，并检查索引加法的溢出边界。
2. 根据已交付位置与字节流剩余容量计算接收窗口，截断窗口外的数据。
3. 定位已有区间，仅存储尚未收到的字节，避免重复与重叠数据占用多份空间。
   完整子串可直接保存时使用移动语义，避免额外复制。
4. 空洞补齐后，立即把连续区间交付给 ByteStream，并移除交付后的暂存区间。
5. 连续交付到结束位置后关闭输出；读取方读完缓冲区后才到达 EOF。

窗口右边界等价于“已读出字节数 + 总容量”，所以已重组但未读出的数据
与乱序暂存数据共同受容量约束。count_bytes_pending() 直接累加区间长度，
不额外维护计数状态，避免重复插入与交付时发生计数更新不同步。

## 方案比较

逐字节有序映射实现简单，但每个字节都有节点与查找成本。
环形缓冲区配合到达标记可减少节点开销，但要维护索引回绕与标记复用。
按子串分块的有序映射便于处理任意乱序与重叠，且无需反复拼接相邻字符串。

设暂存区间数为 N，本次覆盖 K 个已有区间，定位和扫描约为
O(log N + K)，另加新接收字节的复制成本；查询待重组字节数为 O(N)。
容量限制针对数据字节数，容器节点另有内存开销。

## 测试与结果

在项目根目录的 Ubuntu 终端执行：

```bash
cmake -S . -B build/wsl
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check1
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target check0
CMAKE_BUILD_PARALLEL_LEVEL=4 cmake --build build/wsl --target tidy
clang-format --dry-run --Werror src/reassembler.hh src/reassembler.cc
```

- check1 的 18 项检查全部通过，包括地址/未定义行为检测、字节流回归、
  重组器功能、随机乱序窗口、优化构建与性能基准。
- check0 的 11 项检查全部通过，包括远端 HTTP 网页获取。
- 所有 src 文件通过 clang-tidy-20，新增实现通过格式检查。
- 官方用例覆盖空流、乱序、重复、重叠、容量截断、提前结束标志、
  动态窗口及接近 UINT64_MAX 的索引等情形。

官方基准在无重叠、十倍重叠场景分别输出 90.21、15.05 Gbit/s。
其计算分子使用 num_chunks × capacity，实际输入为 num_chunks × chunk_size。
按实际数据量乘以 1500 / 32768 折算，约为 4.13、0.69 Gbit/s，
均超过 0.1 Gbit/s。未修改官方测试的计算方式。

完整日志、验证摘要和实际代码截图见 [check1-screenshots](check1-screenshots/)。

## 实现协助

由 Codex 根据用户“完成 point1”的请求辅助实现、测试并整理记录。
