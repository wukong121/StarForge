# StarForge：星际1强化学习项目设计

## 目标与范围

长期目标：训练能在《StarCraft: Brood War》1v1 完整对局中与 Pluto 对抗的 RL agent。
用户授权先制定计划、随后执行。首个里程碑是可验证的工程起点，不承诺在一次开发中获得竞技级策略。

当前机器是 ARM64 Windows（检测到 build 26300）；用户尚未安装游戏及 BWAPI。
因此将 Python 策略、学习、评测与 32 位游戏进程隔离。先交付本机可运行的核心和游戏桥接源码。
未能进行真实游戏联调时必须明确标记，不把合成环境成绩视为星际胜率。

## 已核实资料（2026-10-22）

- [Pluto 官方](https://github.com/tscmoo/pluto)：全局单网络自博弈 RL，支持三族；目前仅公开运行二进制。
  当日直接读取 README 为 v2.0 / `md09b_1331000`，搜索缓存中的 CoG 版本已落后。
  本项目不声称已验证“当前世界最强”的排名。
- [BWAPI 4.4.0](https://bwapi.github.io/)：接口面向 StarCraft 1.16.1。
- [Windows ARM 仿真](https://learn.microsoft.com/en-gb/windows/arm/apps-on-arm-program-compat-troubleshooter)：
  新版 Prism 支持 x86/x64 和 AVX2。Pluto 官方要求 x86-64 AVX2；ARM 上组合兼容性仍需实测。
- [TorchCraft](https://github.com/TorchCraft/TorchCraft) 和
  [OpenBW 接口](https://github.com/TorchCraft/TorchCraft/blob/main/docs/user/openbw.md) 是后续吞吐量实验候选，
  不假定它们可直接加载 Pluto Windows 二进制，也不在此里程碑引入其旧版依赖。

## 技术决策（实施者选择，可后续调整）

- Python >=3.11、标准库实现第一版：Windows ARM/x64 与 Linux 可使用同一核心；无需 CUDA。
- 首个可解释基线为 masked tabular Q-learning；它用于打通真实 RL 更新流程，非最终竞技架构。
- 人族、1v1、矿物经济和步兵开局；动作是 wait/train_worker/build_supply/build_barracks/train_marine/attack。
- 规则执行器管理闲置工人采矿、建造位置和目标选择；RL 决定动作。该版本是混合 agent。
- C++17 BWAPI 4.4.0 DLL 编译目标必须为 Win32，不能把 ARM64 DLL 注入 32 位游戏。
- JSON Lines 观测 + `ACT <sequence> <action_id>\n` 响应；默认只监听 127.0.0.1:8765。
  远程游戏端通过隧道连接各自 localhost；此阶段不实现公网服务、认证或云部署。
- 决策间隔 24 游戏帧；记录帧数、执行失败和推理耗时。Pluto 对标前再统一动作频率规则。
- 主训练奖励仅来自终局 win=+1/loss=-1/draw=0；不把增加工人等行为人为包装成游戏胜利。

## 首个里程碑交付

1. 严格观测协议：版本、递增序号、frame、资源、人口（BWAPI 的双倍单位）、单位计数、
   可用动作、地图、对手标签、终局结果；不传未发现敌军或真实敌人出生点。
2. Q-learning：合法动作遮罩、固定随机种子、JSON checkpoint、版本检查、终局不 bootstrap；
   eval 不更新 checkpoint。学习率和探索率可配置，参数越界拒绝。
3. 合成 smoke 环境：最小经济/军队策略测试夹具，明显标注 synthetic；
   训练、保存、重载和评测可在没有游戏时演示。它不是星际模拟器。
4. Python policy server：一条连接一局，首帧开始、终帧结算；超时/断开/坏数据记 error，
   不学习虚构终局、不算作真实胜负。允许下一局重新连接。
5. 对局 JSONL + 汇总：wins/losses/draws/errors/truncations、已完成局胜率及 Wilson 95% 区间；
   synthetic 与 broodwar、不同地图及对手版本分别统计。记录 seed（未知为 null）、
   checkpoint SHA256、对手版本标签、时间和 backend，防止误用基准。
6. Win32 BWAPI DLL 源码 + CMake：按协议发送自身和可见敌军统计，执行宏观动作；
   无 CompleteMapInformation，超时退出连接，失败可诊断。游戏启动/重开由用户或后续 runner 负责。
7. README、ARM/x64 安装路线、doctor 命令、测试与验证日志。

## 后续路线与验收

- M1 真机：验证 1.16.1 → BWAPI 示例 → StarForge → Pluto 的兼容性顺序。
  ARM 若失败，将游戏 worker 移至 x64 Windows；不要先投入大规模训练。
  连续 20 局自动采集、无协议死锁，保存可复查回放；再测每秒游戏帧吞吐。
- M2 学习：实体/空间观测、带记忆的策略网络、masked recurrent PPO；先验证单族可学习性，
  对比随机和脚本策略，检查信息泄漏与奖励投机。
- M3 规模：多个游戏 worker、自博弈历史池、课程和独立测试地图；据吞吐与学习曲线决定 CPU/GPU 预算。
- M4 Pluto：锁定二进制 SHA256、地图池、种族和出生位置设置；建议每个 matchup 至少 200 局，
  报告区间、异常率、动作限制。胜率要求由实测阶段再确定；“高于 50%”需考虑统计不确定性。

## 非目标与已知限制

本次不下载或分发游戏资源，不申请收费算力，不宣称已复现 Pluto，不实现三族端到端自博弈。
表格状态离散化有严重混叠、部分可观测性和长时序稀疏奖励问题；它只适合工程基线。
合成环境的 checkpoint 不能作为训练好的星际策略使用；元数据必须区分 backend。
游戏桥接即使编译通过，也不能代替安装游戏后的实机验收。
