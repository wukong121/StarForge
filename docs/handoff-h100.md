# H100 开发交接

日期：2026-10-23。本文是后续 agent 的入口，不是已完成的 Linux 部署报告。

## 用户意图

做一个《星际争霸：母巢之战》RL agent，以 Pluto 为长期竞技对标。
用户已有 Linux x86-64 H100 开发机，希望在那台机器继续开发。本次仅交付
架构与实施计划，不安装软件、不远程连接、不启动 GPU 训练。

推荐下一会话直接使用这段指令：

> 阅读 AGENTS.md 和 docs/handoff-h100.md，按 2026-10-23 H100 设计与实施计划继续开发。
> 先核实目标机、运行现有测试，然后完成第一个未完成任务。按验收门槛逐步推进，
> 把执行证据和下一步写回交接文档。不要把 synthetic smoke 当作星际训练结果；
> 遇到缺失游戏资源或编译工具链时说明具体缺什么，并继续能够独立验证的工作。

## 硬件证据与待核实项

以下来自用户粘贴的输出，尚未通过本项目工具远程核验：

| 项目 | 已知 |
|---|---|
| GPU | 1× NVIDIA H100 NVL，nvidia-smi 显示 95,830 MiB 显存，MIG disabled |
| 驱动 | 615.71.10；界面显示 CUDA UMD 13.4 |
| CPU | x86_64；40 个在线逻辑 CPU、每核一线程；AMD EPYC 9V84 型号字符串 |
| 指令集 | 可见 AVX2、AVX-512、AVX512_VNNI 等标志 |
| RAM | 314 GiB 总内存；无 swap |
| 虚拟化 | Microsoft hypervisor；操作系统只分配了 40 个 CPU，不能按型号中的 96 核配额计算 |

尚不清楚：发行版、容器/cgroup 限额、sudo、磁盘容量/性能/持久性、网络代理、
游戏/BWAPI 是否已安装、是否有可用 Windows 构建机。`nvidia-smi` 的 CUDA 字段
不证明安装了对应 toolkit 或 PyTorch；不要据此强制安装 CUDA 13.4 或升级驱动。

## 当前代码实际状态

- `starforge/agent.py`：masked tabular Q-learning，JSON checkpoint。
- `starforge/protocol.py`：v1 聚合观测、6 个宏观动作，人口用 BWAPI 双倍单位。
- `starforge/server.py`、`__main__.py`：串行 localhost TCP 服务，一连接一局；不会启动游戏。
- `starforge/synthetic.py`、`training.py`：合成夹具，不是 SC1 模拟器。
- `starforge/metrics.py`：基础分组指标、Wilson 区间和 checkpoint 来源。
- `native/StarForge.cpp`：人族混合基线，规则采矿/选址/目标选择；固定 24 帧决策、
  127.0.0.1:8765、5 秒 socket 超时。
- `native/CMakeLists.txt`：要求 Windows/MSVC/Win32，尚未成功编译；不能直接在 Linux cmake 构建。
- 无 PyTorch、PPO、实体网络、runner、自动重开、多 worker、自博弈或已训练星际模型。
- 2026-10-22 Windows 记录：31 个测试通过；无真实星际对局、无验证过的 DLL。

`runs/initial-smoke/` 的成绩只是历史本地夹具结果；runs 被忽略，迁移后可能不存在。
不要使用缺失的实验文件作为后续任务前置条件。

## 搬运与 Git

用户已指定远端：`git@github.com:wukong121/StarForge.git`，
网页地址：[wukong121/StarForge](https://github.com/wukong121/StarForge)。

2026-10-23 用户明确授权提交和推送。此前审批服务错误已经解除，origin 已配置：
fetch 使用上述 SSH 地址，push 使用 `https://github.com/wukong121/StarForge.git`。
原因是当前 Windows 主机 SSH 返回 `Permission denied (publickey)`，HTTPS 可以访问。
通过 HTTPS 检查远端 HEAD/分支时返回成功且无 refs，初始发布分支定为 `main`。
发布结果以实际 Git log/status 和远端 refs 为准；不使用 force-push。

H100 上首次使用（需那台机器已配置 GitHub SSH 访问）：

```bash
git clone git@github.com:wukong121/StarForge.git
cd StarForge
```

也可用 HTTPS：`git clone https://github.com/wukong121/StarForge.git`，私有仓库需相应认证。
已有 checkout 则先确认 origin 和工作区状态，再按实际分支同步，不在非空目录重复 clone。

应包含：AGENTS.md、README.md、pyproject.toml、.gitignore、starforge/、native/、tests/、
scripts/、docs/。排除 `.venv/`、`build/`、`runs/`、缓存、游戏资源和密钥。
Linux 上重新建 venv，不能复制 Windows venv 或 CMake build 目录。

## 首次接手可立即运行的命令

以下是已有命令，不依赖未来计划中的新 CLI。先确认 Python >=3.11；若没有，
记录实际发行版并在获得目标机适用的安装权限后准备独立解释器。

```bash
pwd
git status --short
cat /etc/os-release
uname -m
lscpu
free -h
df -h .
nvidia-smi
python3 --version
python3 -m starforge doctor
python3 -m unittest discover -s tests -v
python3 -m starforge smoke --out "runs/handoff-$(date -u +%Y%m%dT%H%M%SZ)"
```

若目录是直接复制而非 Git checkout，git status 失败只影响版本控制，不妨碍 Python 验证。
不要将当前 `doctor` 当作 Wine/GPU/游戏运行验证；它只做有限的平台和文件检查。

## 从哪里继续

1. 读 [架构设计](superpowers/specs/2026-10-23-h100-architecture-design.md)。
2. 按 [实施计划](superpowers/plans/2026-10-23-h100-development.md) Task 0 开始。
3. 首个目标：保存主机诊断，解决可复现的 Win32 DLL 构建与 Wine/BWAPI Example 运行。
4. 随后交付一场有回放的 StarForge 真实对局，再做 20 局自动重开。
5. 第一个 GPU 目标是小型 masked PPO 正确性及真实轨迹更新；不是立刻训练 315M 网络。

缺游戏时：明确需要可使用的 1.16.1 安装资源和实际路径；不要拿重制版客户端代替。
可先完成 runner 故障夹具、v2 协议与 PPO 数学测试，但真实对局验收必须保持未勾选。

## 后续每次交接需更新

- 当前已完成 Task / 下一个 Task，代码版本或工作区状态。
- 实际通过/失败的命令、日志/回放/manifest 路径，不粘贴秘密。
- 游戏、BWAPI、Wine、编译器、PyTorch/CUDA runtime 的版本和关键文件 SHA256。
- 真实吞吐与动作延迟，错误和截断数量；若没有真实对局就明确写“未验证”。
- 当前阻塞的准确环节及还能推进的工作。

当前下一任务：**Task 0，目标机环境与基线验证。所有 H100 实施任务均未执行。**
