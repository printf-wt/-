# Point 7 离线交付包

`cs144-point7-offline-20261125.zip` 用于这次实际三机联调，约 2.5 MB。
包含 143 个文件：编译所需源码、聊天/UDP 工具、Ubuntu x86_64 已编译端点和启动说明。
源码基于提交 `6b327c9d010c7de04cc0089a94737ee0a36c2bfe`，不包含 Git 凭据或其他本地修改。

两位端点已确认使用 Ubuntu 24.04.5、GCC 13.3、CMake 3.28.3。
已对 ZIP CRC、各文件 SHA-256、脚本 LF、Unix 执行权限及包内程序启动进行检查。
`cs144-point7-offline-20261125-verification.json` 保存交付包整体哈希和检查摘要。

在 Ubuntu 中将包内文件夹提取到 Home，按 `OFFLINE-START.md` 操作。
预编译程序仍需要相应系统运行库，其他发行版或架构优先使用包内源码构建。
包内 IP 是 2026-11-25 本次配置，换网络后需要重新核对。
