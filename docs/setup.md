# 环境准备与游戏验收

## 1. 本机开发

Python >=3.11，无需安装 PyTorch、CUDA 或 Gym。根目录下运行 `./scripts/python.ps1 -m starforge doctor`。
本次机器为 ARM64 Windows build 26300，Codex 自带 Python 是 x64 进程，可通过 Prism 运行。
后续也可安装原生 ARM64 Python，重新运行测试；当前证据只覆盖本次使用的解释器。

## 2. 游戏端逐级验证

按顺序验证，不跳过中间步骤：

1. 准备合法来源的 **StarCraft: Brood War 1.16.1** 和完整游戏资源。
   重制版/当前 Battle.net 客户端不能直接视作 BWAPI 4.4.0 环境。
2. 从 [BWAPI 官方发布](https://github.com/bwapi/bwapi/releases/tag/v4.4.0) 准备 4.4.0。
   SDK 与游戏运行时是不同用途：编译需 `include/BWAPI.h`、`lib/BWAPI.lib`，运行需 BWAPI 注入器与配置。
3. 先按 [BWAPI 官方教程](https://bwapi.github.io/) 启动 ExampleAIModule，验证观察和发出命令。
4. 编译 StarForge，运行一场人族 1v1，确认 JSONL 有终局记录，检查游戏回放和桥接执行失败日志。
5. 最后安装 [Pluto 官方 release](https://github.com/tscmoo/pluto/releases)，用独立游戏实例对战。
   不要把两个 bot DLL 配成同一个游戏实例的 agent。

ARM Windows 的 Prism 支持 AVX2 仿真不等于上述组合兼容。若步骤 1–3 或 Pluto 不工作，
优先迁移游戏 worker 至 x64 Windows，再用隧道连接 Python 服务。暂不为此自动创建云资源。

## 3. 编译 Win32 模块

安装 MSVC C++ 桌面工具、Windows SDK、CMake，以及 x86 编译工具。ARM 主机要包含交叉编译工具。
推荐使用 [可复现构建流程](native-build.md)，在 Windows 仓库根目录执行：

```powershell
./scripts/build-native.ps1
```

官方 4.4.0 包不提供预编译 `.lib`，脚本先从匹配 SDK 构建 Release/Win32
`BWAPILIB.lib` 和官方示例，再构建桥接与加载探针；不能直接寻找 `lib/BWAPI.lib`。
若手动运行 CMake，必须同时指定 SDK 的 `BWAPI_ROOT` 和已构建库的
`BWAPI_LIBRARY`，具体命令、工具版本及验证边界见上述构建指南。
Windows 构建、Wine 加载及实际游戏加载是三个独立验收项，当前结果见验证记录。

把构建出的 `StarForge.dll` 放到游戏目录的 `bwapi-data/AI/`，在已有 `bwapi-data/bwapi.ini` 中
将 AI 路径设为 `bwapi-data/AI/StarForge.dll`，种族设为 Terran。保留配置备份，按官方启动流程加载。
确保 `bwapi-data/write/` 可写；日志为 `starforge-bridge.log`。

先启动 Python `serve` 再启动游戏。DLL 固定连接 localhost:8765，Python 默认相同。
DLL 的收发超时是 5 秒；Python `--timeout` 控制等待连接和观测的空闲超时，不调整 DLL 超时。
桥接每 24 帧请求一次动作。首个版本为同步、单 worker，只适合功能联调。

## 4. 两台机器的分工

Python 与游戏模块通过字节协议通信，不要求相同 CPU 架构。把游戏端的 `127.0.0.1:8765`
通过已有 SSH/VPN 隧道转发到学习端的 `127.0.0.1:8765`，即可复用同一接口。
当前服务无认证，设计为仅本机监听；不直接开放公网端口。

## 5. 真机验收清单

- 连续 20 局有完整记录与可复查回放；检查终局、主动退出和超时分类。
- 核对人口使用 BWAPI 双倍数值，单位与可见敌军统计不泄漏战争迷雾。
- 检查执行失败日志，确认建造、采矿、生产、攻击确实发生。
- 测量游戏帧/秒、对局/小时、动作延迟、CPU 与内存，再决定 worker 数量。
- 比较随机策略、固定规则基线和学习策略；合成策略不能进入真实评测。
- 对标 Pluto 前，锁定 release、双方二进制和地图哈希、对局规则、种族组合、出生位置与回放。

自动重开、对手调度、回放收集、多 worker 和训练 GPU 后端尚未实现。
