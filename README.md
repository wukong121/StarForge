# StarForge

面向《星际争霸：母巢之战》的强化学习 agent 项目，以 **Pluto** 为长期竞技对标。

**当前状态：工程基础版。** 已有可运行的 Python 学习、策略服务、模型保存和评测工具，
以及待编译/联调的 BWAPI 游戏桥接源码。尚未打过真实星际对局，也没有训练好的竞技模型。

**Linux H100 接续开发：** 从 [开发交接](docs/handoff-h100.md) 开始阅读，随后查看
[H100 架构设计](docs/superpowers/specs/2026-10-23-h100-architecture-design.md) 和
[分阶段实施计划](docs/superpowers/plans/2026-10-23-h100-development.md)。根目录 `AGENTS.md`
提供 agent 入口。新文档是待执行计划；目前尚无已验证的 Linux 游戏环境或 PPO 实现。

## 现在能运行什么

Python 3.11+，核心无需第三方依赖。在项目根目录运行：

```powershell
./scripts/python.ps1 -m starforge doctor
./scripts/python.ps1 -m unittest discover -s tests -v
./scripts/python.ps1 -m starforge smoke
```

若已有 Python，也可以把 `./scripts/python.ps1` 替换为 `python`。
脚本依次寻找项目 `.venv`、PATH 中的 Python、Codex 自带 Python；不会自动安装软件。

`smoke` 默认进行 4,000 次合成训练，再用不同种子分别评测学习策略和随机策略各 200 次。
输出目录是 `runs/smoke-<时间>/`，含 `checkpoint.json`、`matches.jsonl`、`report.json`、`config.json`。
合成环境只是验证接口和学习更新的简化任务，**其胜率与星际或 Pluto 胜率没有对应关系**。

```powershell
./scripts/python.ps1 -m starforge smoke --episodes 4000 --eval-episodes 200 --seed 11 --out runs/my-experiment
./scripts/python.ps1 -m starforge report runs/my-experiment/matches.jsonl
```

指定的输出目录必须为空，避免覆盖实验。模型存储 backend 标签；合成模型不能加载到游戏服务。

## 路线

| 阶段 | 交付/验收 | 当前状态 |
|---|---|---|
| 工程基础 | 协议、masked Q-learning、smoke、JSONL、统计和诊断 | 已实现，见验证记录 |
| 游戏接入 | 1.16.1 + BWAPI 4.4.0、Win32 桥接、真实对局回放 | 桥接源码已写，编译及实机待验证 |
| 学习能力 | 人族基线 → 实体/空间观测和 recurrent PPO | 设计路线，未实现 |
| 规模化训练 | 多 worker、同步最新策略自博弈、训练/测试地图隔离；历史池作为后续实验 | 未实现 |
| Pluto 对标 | 固定模型版本与 SHA256、地图与 matchup、足够局数及置信区间 | 未开始 |

第一版由 RL 从 `wait / train_worker / build_supply / build_barracks / train_marine / attack` 中选择动作。
规则负责采矿、建造位置与攻击目标；这是混合基线。表格 Q-learning 不解决星际全部状态空间，
后续需要替换策略表示并扩大动作空间。

## ARM64 Windows

可以用这台电脑开发、运行测试和小规模 CPU 实验。本次使用 x64 Python 经 Prism 运行，
诊断命令分别报告 ARM64 系统和 x64 进程。无需先购买 GPU 或更换电脑。

游戏及 Pluto 的兼容性需要单独实测。微软新版 Prism 支持 x86/x64 及 AVX2，但这不证明 BWAPI
注入和 Pluto 组合可用。游戏桥接必须编译为 **Win32/x86**。必要时让 x64 Windows 机器运行游戏，
本机负责开发与控制；规模化 GPU 训练留到吞吐量与模型方案明确后。

## 游戏接入（需要先准备游戏与 SDK）

完整步骤见 [安装说明](docs/setup.md)。简要流程：编译 `native/StarForge.cpp`，
将 DLL 配置为 BWAPI bot，再启动策略服务和人族游戏：

```powershell
./scripts/python.ps1 -m starforge serve --mode train --episodes 1 --timeout 120 --opponent builtin --opponent-version sc1161
```

服务只监听 `127.0.0.1:8765`，不会启动游戏或自动重开。每一局由一个桥接连接提供；
将 `--episodes` 增大前，应准备手动或外部 runner 重开游戏。当前串行处理对局。

真实模型默认保存到 `runs/broodwar/checkpoint.json`。评测使用 `--mode eval`，不更新模型：

```powershell
./scripts/python.ps1 -m starforge serve --mode eval --checkpoint runs/broodwar/checkpoint.json --opponent Pluto --opponent-version v2.0-md09b_1331000 --timeout 120
```

`--opponent` 与 `--opponent-version` 是操作者提供的标签，服务不能验证对手身份。
正式 benchmark 还必须保存双方 DLL/模型哈希、地图哈希、出生位置、比赛规则及回放。
当前日志提供基础可追溯性，尚不构成完整赛事运行器。

## 文档

- [H100 开发交接与首次命令](docs/handoff-h100.md)
- [H100 架构设计](docs/superpowers/specs/2026-10-23-h100-architecture-design.md)
- [H100 实施计划](docs/superpowers/plans/2026-10-23-h100-development.md)
- [设计与长期目标](docs/superpowers/specs/2026-10-22-starforge-design.md)
- [实施计划](docs/superpowers/plans/2026-10-22-starforge-foundation.md)
- [游戏安装与 ARM 路线](docs/setup.md)
- [协议和对局生命周期](docs/protocol.md)
- [验证证据与限制](docs/validation.md)
- [实施记录](docs/implementation-log.md)

参考：[Pluto 官方](https://github.com/tscmoo/pluto)、[BWAPI](https://bwapi.github.io/)、
[Windows ARM 仿真设置](https://learn.microsoft.com/en-gb/windows/arm/apps-on-arm-program-compat-troubleshooter)。
2026-10-22 直接读取 Pluto README 为 v2.0 / `md09b_1331000`；该仓库只发布推理二进制，未提供训练源码。
