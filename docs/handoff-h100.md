# H100 开发交接

日期：2026-10-23。本文是后续 agent 的入口。Linux Task 0 的主机诊断与 Python 基线
已落地；路径 1 的环境、MSVC 构建与 Wine 模块探针也已通过。这仍不是已完成的
真实游戏部署或训练报告。

## 路径 1 最新进度：Task 1 部分完成

- 用户授权尝试官方下载游戏，并明确授权独立分支的 Windows MSVC CI 构建。
  当前分支 `native/wine-route1`，实现提交 `287aee0`；**没有合并 main**，
  main 的交接提交仍为 `4cbed7e`。
- 安装 Ubuntu Wine 9.0 amd64/i386、Xvfb 21.1.12、X11 查询工具、CMake 3.28.3、
  7-Zip。启用 i386；只更新了七个必要的匹配多架构基础依赖，未删除软件包、
  未修改 GPU/kernel 包、未升级 NVIDIA 驱动（仍 615.71.10）。
- 无物理显示器的 Xvfb 响应正常；在一次性 win64 prefix 中，PE32+ x64 和
  PE32 x86 cmd 都返回精确标记，Win32 Notepad 窗口出现。保留了初始目录、
  COM/RpcSs bootstrap 错误日志，不能据此声称完整 Windows/游戏兼容。
- 官方免费安装链接实际返回 Battle.net Setup 2.0.0.4232，**不是 1.16.1 游戏安装**。
  未使用不明整合包、自动登录或非官方降级。合法的 1.16.1 完整资源仍缺失。
- 官方 BWAPI 4.4.0 已下载到 Git 外。实测 SDK 不含预编译 `.lib` 或示例 DLL；
  修正 CMake 的旧假设，先构建同 SDK 的 `BWAPILIB.lib` 再链接。
- [Windows 原生构建](https://github.com/wukong121/StarForge/actions/runs/39926874158)
  与 Python CI 矩阵通过。MSVC tools 14.44.35207 构建官方示例、StarForge、
  StarForgeProbe；PE32/i386、精确导出、正负加载用例通过。
- 产物 SHA256/来源核验后，在 H100 的 Wine 上实际加载了两个 MSVC DLL，解析入口、
  `gameInit(nullptr)`、创建/销毁 AIModule 和卸载均通过；三个拒绝用例也通过。
  **没有调用任何游戏回调、没有启动游戏、没有 replay，G1 未通过。**
- Wine 探针都只停止自己记录的进程，并移除了临时 prefix。运行证据、包版本、
  下载/产物实际位置索引在 `runs/route1-20261023T083536Z/`，均被 Git 忽略。
  SDK、游戏安装器和编译产物均未提交；CI artifact 保留七天，本地另存 Git 外。
- 外部数据根和持久性尚未确定。已确认一个挂载卷有云厂商数据丢失警告，没有使用
  或修改它；不自动格式化设备、不启动长跑。系统卷当前约 20 GiB 可用。

**下一步仅缺外部游戏资产才能推进真实验收：**准备合法 1.16.1 完整安装目录，
包含正确版本的 `StarCraft.exe`、`Storm.dll`、三个 MPQ 和可用地图；实际目录由用户
提供。先验证官方示例的注入/命令/回放，再接入 StarForge，不能用加载探针替代。
操作与边界见 [原生构建](native-build.md)、[Linux 指南](linux-runtime.md)、
[验证记录](validation.md)。

## Task 0 验证与历史交接

- 起点版本 `4027240`；Task 0 实现与工程工具链已独立提交为 `8299994`。
  用户确认沿用已有作者身份，仅配置当前仓库，没有修改全局 Git 设置。
- 已实现 `runtime.host.probe_host()`，`doctor` 保留旧字段并新增分状态主机诊断。
  覆盖 cgroup v2 父级限额、CPU affinity、内存/磁盘和有超时的外部工具查询。
- 使用 uv 0.13.5/锁文件、Hatchling、Ruff、mypy；标准库 CLI 和无依赖安装保留。
  Linux/Windows CI 已配置并在 GitHub 通过，后续原生构建结果见上方最新进度。
  此主机 uv 位于忽略目录 `.cache/tools/uv`，未全局安装；新 shell 可直接调用它，
  或临时 `export PATH="$PWD/.cache/tools:$PATH"` 后使用文档中的 uv 命令。
- 实际核实 Ubuntu 24.04.5、40 CPU、约 314.68 GiB RAM、H100 NVL 95,830 MiB。
  当前可见 cgroup 层级无额外有限 CPU/RAM 配额；不等于保证性能或隐藏父级无限额。
- 系统盘约 23 GiB 可用；另有挂载数据卷，但持久性未知。训练资产必须先确定
  外部数据根与持久性；未格式化/挂载任何设备。
- Task 0 初始时 Wine/Xvfb/CMake 未在 PATH，游戏与 SDK/构建通路尚未提供。
  后续环境/构建/模块加载已解决，见上方最新进度；仍没有真实游戏或 torch/CUDA 运算证据。
- 主机证据：`runs/task0-host-20261023T075145Z/`；基线 smoke：
  `runs/task0-baseline-20261023T074755Z/`，仅 synthetic。运行命令和最终测试结果见
  [验证记录](validation.md)；开发/恢复方法见 [Linux 指南](linux-runtime.md)。
- 最终 stdlib suite：53 测试通过（新增 22 个主机测试），Ruff/mypy/构建及无依赖
  安装验证通过；`runs/task0-final-20261023T075708Z/` 的完整 synthetic smoke
  与基线 checkpoint 字节 hash 一致，不代表真实星际技能。

Task 0 时的下一步是 **Task 1 的真实资产与 ABI 兼容构建通路核实**。Task 0 的实现、验证与提交
已完成；游戏缺失不妨碍随后推进独立协议/runner fixture/PPO 数学测试。

## 用户意图

做一个《星际争霸：母巢之战》RL agent，以 Pluto 为长期竞技对标。
用户已有 Linux x86-64 H100 开发机，希望在那台机器继续开发。此前 Windows 会话仅交付架构与实施计划；当前 Linux 会话已开始 Task 0，
只安装项目隔离的开发工具，不启动 GPU 训练。

推荐下一会话直接使用这段指令：

> 阅读 AGENTS.md 和 docs/handoff-h100.md，按 2026-10-23 H100 设计与实施计划继续开发。
> 先核实目标机、运行现有测试，然后完成第一个未完成任务。按验收门槛逐步推进，
> 把执行证据和下一步写回交接文档。不要把 synthetic smoke 当作星际训练结果；
> 遇到缺失游戏资源或编译工具链时说明具体缺什么，并继续能够独立验证的工作。

## 原始硬件交接与待核实项

以下是此前用户粘贴的硬件记录；当前 Linux 实测结果以上方最新进度和验证记录为准：

| 项目 | 已知 |
|---|---|
| GPU | 1× NVIDIA H100 NVL，nvidia-smi 显示 95,830 MiB 显存，MIG disabled |
| 驱动 | 615.71.10；界面显示 CUDA UMD 13.4 |
| CPU | x86_64；40 个在线逻辑 CPU、每核一线程；AMD EPYC 9V84 型号字符串 |
| 指令集 | 可见 AVX2、AVX-512、AVX512_VNNI 等标志 |
| RAM | 314 GiB 总内存；无 swap |
| 虚拟化 | Microsoft hypervisor；操作系统只分配了 40 个 CPU，不能按型号中的 96 核配额计算 |

已核实发行版、可见 cgroup 限额、磁盘容量，本次 `sudo -n` 成功，BWAPI 与 Windows CI
构建通路已验证；磁盘性能/持久性、游戏实际目录仍未确认。`nvidia-smi` 的 CUDA 字段
不证明安装了对应 toolkit 或 PyTorch；不要据此强制安装 CUDA 13.4 或升级驱动。

## 当前代码实际状态

- `starforge/agent.py`：masked tabular Q-learning，JSON checkpoint。
- `starforge/protocol.py`：v1 聚合观测、6 个宏观动作，人口用 BWAPI 双倍单位。
- `starforge/server.py`、`__main__.py`：串行 localhost TCP 服务，一连接一局；不会启动游戏。
- `starforge/synthetic.py`、`training.py`：合成夹具，不是 SC1 模拟器。
- `starforge/metrics.py`：基础分组指标、Wilson 区间和 checkpoint 来源。
- `starforge/runtime/host.py`：Task 0 只读主机诊断；`doctor.runtime` 有明确
  available/unknown/error 状态，不安装工具或导入 torch。
- `native/StarForge.cpp`：人族混合基线，规则采矿/选址/目标选择；固定 24 帧决策、
  127.0.0.1:8765、5 秒 socket 超时。
- `native/CMakeLists.txt`：保留 Windows/MSVC/Win32 闸门，匹配 SDK 的 Release
  BWAPILIB 静态库构建已通过；不在 Linux 用 GCC/MinGW 编译 BWAPI bot DLL。
- `native/BridgeProbe.cpp`、`scripts/build-native.ps1`、原生 CI：
  构建、PE/导出和无游戏模块生命周期验证；不是游戏 launcher 或注入验证。
- 无 PyTorch、PPO、实体网络、runner、自动重开、多 worker、自博弈或已训练星际模型。
- 2026-10-22 Windows 记录：31 个测试通过；无真实星际对局、无验证过的 DLL。
- 2026-10-23 Linux 已通过旧 31 测试并完成新增诊断回归；最终数量和命令见验证记录。

`runs/initial-smoke/` 的成绩只是历史本地夹具结果；runs 被忽略，迁移后可能不存在。
不要使用缺失的实验文件作为后续任务前置条件。

## 搬运与 Git

当前 Linux checkout 的 Task 0 实现提交是 `8299994`，基线为 `4027240`。
实际 origin fetch/push 都使用用户指定的 SSH URL；发布前 SSH 查询成功，
远端 main 为 `4027240`。用户已授权本次提交与正常 push，发布结果以实际 refs 为准。
下述 Windows 发布过程仅保留为历史，不代表当前远端配置。

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
2. 按 [实施计划](superpowers/plans/2026-10-23-h100-development.md) 查看 Task 0/Task 1
   已记录证据；先核实当前独立分支，不要重复安装或覆盖已存在的本地运行目录。
3. 下一目标：获得合法 1.16.1 游戏目录，验证官方 Example 的游戏加载/命令/回放。
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

当前下一任务：**Task 1，补齐 1.16.1 游戏资源，验证 Example/StarForge 真实对局。**
Task 0 已完成；Task 1 的编译与 Windows/Wine 模块加载通过，数据盘持久性仍 unknown。
Task 1–9 的真实游戏/学习验收尚未执行，不能用 Python/模块探针替代。
