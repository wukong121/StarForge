# StarForge H100 Development Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement task-by-task if that
> skill is available. Otherwise follow the task interfaces and acceptance gates directly.
> Do not require a specific agent vendor or skill installation to continue. Checkboxes track
> actual execution, not completion of this document. Dated execution evidence is in validation.md.

**Goal:** 在已有 H100 Linux 主机上构建可复现的 SC1 对局、采样、PPO 和评测闭环。

**Architecture:** Linux 原生 Python/PyTorch；Wine/Xvfb 游戏客户端通过 Win32 BWAPI DLL
连接本机推理服务。Supervisor 管理隔离的 match，collector 用固定策略版本形成有界
rollout，单 H100 同步更新模型。先保留宏动作基线，再加实体网络和循环记忆。

**Tech Stack:** Python >=3.11；stdlib baseline；optional PyTorch/NumPy training extra；
C++17、MSVC-compatible x86 ABI、BWAPI 4.4.0、SC1 1.16.1、Wine/Xvfb；不引入集群平台。

**Spec:** [H100 架构设计](../specs/2026-10-23-h100-architecture-design.md)。

## Global Constraints

- 用户提供的硬件为 40 个可见 CPU、314 GiB RAM、1× H100 NVL；先核实 cgroup 和磁盘。
- 当前没有已验证 native DLL/真实对局/PPO/runner；Linux Task 0 已实现、记录主机/Python 验证
  并独立提交为 `8299994`，其余任务未实现。
- v1 固定 24 帧/6 宏动作语义保留；v2 单独版本，CLI 新命令均为待实现。
- `synthetic` 与 `broodwar`、`macro_ppo` 与 `entity_ppo`、时序 profile 分别标识。
- 只使用合法玩家观测；终局、截断、错误分离；评测固定权重且不训练。
- 单机严格同步 PPO，版本不混用；双玩家请求不能互等；完整数据记录先于性能优化。
- 不提交游戏资源、SDK/模型二进制、Wine prefix、运行数据、凭据或主机绝对路径。
- 本设计超参数是 StarForge 的建议值，不是 Pluto 复现证据。

## Review Focus

1. 编译成功但 C++ ABI/运行库错误：Task 1 要求实际 BWAPI 加载与游戏命令证据。
2. 双玩家时序不对称、更新暂停被当作卡死：Task 4/8 要求双客户端夹具和真实对局。
3. 时间限制/崩溃产生错误 GAE 或吞掉有效数据：Task 3/5 要求精确 bootstrap/trace 测试。
4. 重启、端口复用、late response 污染新局：Task 2/3 要求身份、seq 和进程归属测试。
5. 空间单位溢出、迷雾和候选动作变化：Task 7 要求显式溢出处理和 mask/执行一致性测试。

## 文件责任和依赖

以下路径均相对仓库根；Create 是计划文件，当前尚不存在。每个新 package 需补 `__init__.py`。
不为了符合目录表提前创建空模块；在所属任务引入。

| 路径 | 责任 |
|---|---|
| `starforge/runtime/host.py` | Linux/cgroup/Wine/GPU/磁盘诊断 |
| `starforge/runtime/config.py` | RunConfig/MatchSpec/ClientSpec 与配置校验 |
| `starforge/runtime/launcher.py` | 外部管理器和自有进程生命周期适配 |
| `starforge/runtime/runner.py` | Match 状态机、超时、重试、回放归档 |
| `starforge/runtime/manifest.py` | 固定实验来源、文件 hash、原子落盘 |
| `starforge/runtime/scheduler.py` | 并发 match、资源预算、对手和地图调度 |
| `starforge/rl/schema.py`, `wire.py` | v2 数据类型与有界 wire parser |
| `starforge/rl/inference.py`, `collector.py` | 推理批处理、版本屏障与 rollout |
| `starforge/rl/advantages.py`, `ppo.py` | GAE 与 masked clipped PPO |
| `starforge/rl/models.py`, `checkpoint.py` | 策略网络与可恢复训练状态 |
| `starforge/rl/features.py`, `actions.py` | 实体/空间编码与条件动作分布 |
| `starforge/rl/train.py`, `evaluate.py` | 有界训练/评测入口，组合前述组件 |
| `native/StarForge.cpp`, `native/BridgeConfig.h`, `native/ProtocolV2.h` | Win32 bridge 配置和 v2 接口 |
| `configs/*.toml`, `docs/linux-runtime.md`, `docs/native-build.md` | 可移植配置与实测操作指南 |
| `tests/test_runtime_*.py`, `tests/test_rl_*.py`, `tests/fixtures/` | 无游戏的回归和双客户端 fixture |

依赖顺序：0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9。
若缺游戏/编译资产，3 的纯协议部分、4 的 fixture、5 的数学可以先做，但不能勾掉真实验收。

---

### Task 0: 核实 H100 主机并重跑当前基线（G0）

**Files:** Create `starforge/runtime/host.py`, `tests/test_runtime_host.py`,
`docs/linux-runtime.md`; Modify `starforge/doctor.py`, `docs/validation.md`, `docs/handoff-h100.md`。

**Interfaces:** `probe_host() -> dict`：返回带 `available/unknown/error` 状态的 JSON-safe
主机、磁盘、cgroup CPU/RAM、GPU、Wine/Xvfb 版本信息；不安装、不修改主机。
`diagnose()` 保留旧字段，新增 `runtime`；未安装 torch 不导致 doctor 失败。

- [x] 执行交接文档里的现有命令；记录实际 OS、基线测试和 smoke 结果。检查 CPU quota、memory.max、数据盘持久性与可用空间。
  2026-10-23：记录于 validation；持久性明确为 unknown，未经外部确认不用于长跑。
- [x] 为缺少 nvidia-smi/Wine、工具超时、cgroup 限额小于 lscpu 编写 fixture 测试：unknown 不能写成 validated，进程失败不崩溃 doctor。
- [x] 运行 `python3 -m unittest discover -s tests -p 'test_runtime_host.py' -v`，确认新测试先失败；实现 bounded subprocess 诊断，再运行通过。
- [x] 文档记录真实发行版适用的依赖准备步骤。不要盲目升级 NVIDIA 驱动；torch 安装时选择官方支持 H100 的 wheel，并单独测 CUDA tensor 运算。
  仅准备隔离开发工具；未安装 torch、未声称 CUDA tensor 验证通过。
- [x] 运行完整 stdlib suite；记录 G0 主机/Python 证据及 uv/Hatchling 构建、无依赖安装验证。
- [x] 为本任务单独 commit：`8299994`。作者身份经用户确认，仅配置当前仓库。

### Task 1: Wine 游戏与可复现 DLL 构建（G1 的前置）

**Files:** Create `docs/native-build.md`; Modify `docs/linux-runtime.md`,
`native/CMakeLists.txt`（只做经过验证的改动），必要时 Create `scripts/build-native.ps1`。

**Interfaces:** 输入实际游戏模板、SDK 和构建工具路径；输出 `StarForge.dll`、
build manifest（compiler/SDK/runtime versions、source revision、SHA256、PE/exports 报告）。
DLL 不入 Git，构建脚本不得嵌入用户私有路径。

- [ ] 核实 SC1 1.16.1 和 BWAPI 4.4.0 实际资产路径；缺失时只请求具体缺项，保留日志并推进独立任务。
- [ ] 先确定 ABI 兼容构建通路。优先现有 Windows MSVC x86；Linux-only 方案需实际加载验证，不能仅将 MSVC 条件放开。
- [ ] 根据已验证通路记录 exact build commands、PE32/i386、`gameInit`/`newAIModule` 导出、运行库依赖、DLL hash。
- [ ] 在目标 Linux 上验证 Wine（32 位游戏和 64 位 Pluto 进程兼容环境）与 Xvfb；根据选用 Wine 版本确定 prefix/WoW64 方案，不能强制全体 WINEARCH=win32。
- [ ] 用官方 ExampleAIModule 启动游戏，证明确实执行游戏命令；保存 Wine、BWAPI 日志和 replay。
- [ ] 启动现有 `python3 -m starforge serve --mode train --episodes 1 --timeout 120 --opponent builtin --opponent-version sc1161`，手动/已验证管理器跑一场 StarForge 人族对局并检查终局、动作、replay。
- [ ] 写入真实命令和哈希；构建通过与运行通过分别标记。此任务无意义不大的编译脚本镜像测试，以实际 ABI/对局验证为验收。

### Task 2: 单 match 自动启动、结束、重开（G2）

**Files:** Create `starforge/runtime/{config,launcher,runner,manifest}.py`,
`configs/runtime.example.toml`, `tests/test_runtime_runner.py`, `tests/fixtures/fake_game.py`,
`native/BridgeConfig.h`; Modify `native/StarForge.cpp`, `starforge/__main__.py`, `docs/linux-runtime.md`。

**Interfaces:**
- `ClientSpec(slot: int, game_dir: Path, wine_prefix: Path, port: int, launch_argv: tuple[str, ...])`。
- `MatchSpec(episode_id: str, clients: tuple[ClientSpec, ...], map_path: Path, opponent: str, max_frames: int)`。
- `RunConfig(data_root: Path, run_id: str, matches: int, max_parallel_matches: int, max_retries: int=2)`。
- `Launcher.start(client: ClientSpec) -> ProcessHandle`; `stop(handle: ProcessHandle) -> None`；
  handle 保存 Popen/进程组、启动时间和所属 run，不能用全局进程名杀进程。
- `MatchRunner.run(spec: MatchSpec) -> MatchResult`；结果含 episode_id、outcome、attempt、
  wall/frame 数据、双方报告、错误、replay/hash。`ManifestWriter` 统一写 result，进程不并发 append 同一 JSONL。
- 新 CLI `python3 -m starforge run --config <toml>`，此任务是首次实现该命令。

- [ ] fixture 复现连接超时、崩溃、正常终局、用户中断和重试；断言 error 不变成 loss、每次 attempt 独立身份、只清理自身进程、重试不超过 2 次。
- [ ] 运行 `python3 -m unittest discover -s tests -p 'test_runtime_runner.py' -v` 确认 RED，再实现状态机/隔离目录/有界 deadline/退出清理。
- [ ] bridge 从实例配置读取 port/decision_frames/timeout/log path（默认保持 8765/24/5000ms）；校验端口 1..65535，JSONL 日志按实例隔离。
- [ ] 将真实验证的比赛管理器包装成 Launcher；记录版本及配置，不写未验证的启动参数。回放从客户端归档到 episode 目录并 hash。
- [ ] fixture GREEN；真实连续 20 局自动重开，有完整结果和可复查 replay、无协议死锁。执行一次受控 kill 所属游戏进程，确认 error 与下一局恢复。
- [ ] 保存 G2 报告/更新文档/commit。20 局不要求赢，不能用 20 条 socket fixture 记录代替。

### Task 3: v2 采样与时序协议

**Files:** Create `starforge/rl/{schema,wire}.py`, `native/ProtocolV2.h`,
`docs/protocol-v2.md`, `tests/test_rl_protocol.py`; Modify bridge、runner 和实例配置。

**Interfaces:**
- `SessionKey(run_id, worker_id, episode_id, player_id)`（前三项 str、player_id int）。
- `ObservationV2(key: SessionKey, seq: int, frame: int, schema: str, features: dict, legal: dict, policy_version: int)`。
- `ActionV2(key, seq, policy_version, branches: dict, sampled_logprob: float)`。
- `Transition(obs, action, old_value: float, reward: float, reward_components: dict,
  terminated: bool, truncated: bool, valid: bool, bootstrap_value: float,
  bootstrap_mask: bool, trace_mask: bool, applied_frame: int | None, command_status: str)`；
  v2 类型完整定义在 schema.py，序列化禁止 NaN/Inf 和 bool-as-int。
- `decode_message(payload: bytes) -> Hello | ObservationV2 | CommandAck | EpisodeEnd`，
  `encode_action(action: ActionV2) -> bytes`；LF JSON 初版限制 4 MiB/帧并有超时，超限立即失败。
- `macro_v1` 特征/动作顺序明确沿用旧协议；握手钉住 features/action/reward/timing profile。

- [ ] 先写 v1 向后兼容和 v2 非法值、超长包、seq 重复、旧 episode、迟到动作、版本不匹配测试；重复响应不得二次执行。
- [ ] 定义 terminal/truncation/error 及 ack 格式；在文档固定字段、单位、特征顺序和状态机，加入往返 fixture。
- [ ] 运行 `python3 -m unittest discover -s tests -p 'test_rl_protocol.py' -v` 确认 RED，再实现 Python parser 与 bridge v2。
- [ ] 实现观测帧/执行帧日志，拒绝执行仍保留原 sampled action/logprob；数据中 command_status 区分失败与终局。
- [ ] 同时维护现有 v1 CLI/tests；用一场 v2 宏动作真实对局核对 replay、seq、动作执行帧和 mask。若游戏暂停/快进语义不同于预期，先更新 timing profile 再往下做。
- [ ] 测试 GREEN，保存 protocol fixture、实际时序报告并 commit。

### Task 4: 多 match、双客户端和有界 collector（G3）

**Files:** Create `starforge/runtime/scheduler.py`, `starforge/rl/{inference,collector}.py`,
`tests/test_runtime_scheduler.py`, `tests/test_rl_collector.py`; Modify runner、config、manifest。

**Interfaces:**
- `Policy.act(observations: list[ObservationV2], states: list[object | None]) -> list[PolicyOutput]`；
  `PolicyOutput(action, logprob: float, value: float, next_state)`；先用固定策略 fixture。
- `InferenceService.publish(policy: Policy, version: int) -> None`；只在 barrier 后发布，
  收到该版本确认才放行；hidden 按 SessionKey 隔离。
- `Collector.collect(policy_version: int, horizon: int=256) -> RolloutBatch`；batch 含
  time/player 维、valid/reset/bootstrap/trace masks、原始观测动作与单一版本。
- `MatchScheduler.run(config: RunConfig) -> RunSummary`；最大并发 match 数和有界 queues 在 config 中声明。

- [ ] 双客户端 fixture：A 慢、B 快；A/B 乱序连接；一方掉线；版本更新中断；断言 B 的当前请求不等待 A 的下一步，其他 match 不受故障污染。
- [ ] 写 barrier 长更新 fixture：正常更新期间暂停 frame deadline，控制 heartbeat 仍有独立 deadline；late response 不落入新 rollout。
- [ ] 运行 `python3 -m unittest discover -s tests -p 'test_rl_collector.py' -v` / `test_runtime_scheduler.py` RED，再实现有界队列、双端服务和调度。
- [ ] 每 match 最多 256 个配对决策轮，每轮先回复双方当前动作，再收集 successor；
  任一方终局/故障则共同结束窗口，在安全边界收尾在途消息。短窗口 padding、无 successor
  的尾步 invalid，双方有效步数可不同。初版不在窗口内开新局补数，早结束 match 等全局更新；
  不得因某玩家不足 256 个有效步而扣住另一方当前动作。测试 1/255/256 轮终止及零有效 batch。
- [ ] 实测多人游戏的暂停/响应屏障，确认无单边推进死锁。若无法可靠暂停，停止扩容，先实现并验证另一种明确的时序协议，不能回退到默许版本混采。
- [ ] 从 1→2→4→8 matches 测量，遇到不稳定档位停止上调；记录两个客户端带来的资源倍数、p95/p99、错误、吞吐和队列峰值。
- [ ] fixture GREEN，选一个稳定档位完成 G3，更新报告/commit；仍不需要训练网络。

### Task 5: masked PPO 数学、checkpoint 与 GPU smoke

**Files:** Create `starforge/rl/{advantages,ppo,models,checkpoint}.py`,
`tests/test_rl_ppo.py`, `tests/test_rl_checkpoint.py`, `configs/ppo-macro.toml`;
Modify `pyproject.toml` 添加 optional `train` extra。

**Interfaces:**
- `compute_gae(rewards, values, next_values, bootstrap_mask, trace_mask, gamma: float, lam: float) -> (advantages, returns)`；
  输入同形 `[T, B]` FP32 tensors，每步 next_value 明确对应可信 successor。
- `MacroActorCritic`：标准化 v1 数值特征 → 2×256 MLP → 6 logits + scalar value；mask 在分布层应用，normalizer 的统计随 checkpoint 保存。
- `PPOTrainer.update(batch: RolloutBatch) -> dict[str, float]`；使用设计 §6 的超参数与 single-version 检查。
- `save_checkpoint(path: Path, state: TrainingState) -> str` / `load_checkpoint(path: Path, expected_schema: str) -> TrainingState`；
  state 含模型/optimizer/RNG/normalizer/config/version/counters，返回值 str 为精确落盘字节 SHA256。

- [ ] 增加 torch extra，保留无依赖安装和旧 CLI；未装 torch 时 RL tests 明确 skip，core tests 仍可运行。
  RL 验收必须在已安装 extra 的环境运行，不能用 skipped 当 passed。保存实际验证依赖版本。
- [ ] 写精确数值测试：gamma=1, lambda=1, rewards=[0,1], values=[0.2,0.3], next_values=[0.3,0],
  bootstrap=[1,0], trace=[1,0]，应得到 advantages=[0.8,0.7]；单步时间限制 r=0,v=.2,next=.4 得 advantage=.2，下一 episode 不串入 trace。
- [ ] 测试非法动作概率严格为 0、全空 mask 非终局报错、单合法动作 entropy=0、ratio=1 时 surrogate 与 advantage 一致、clip 正负优势边界、有效样本归一化不包含 padding。
- [ ] checkpoint 测试：恢复后的下一次更新与同状态对照在 CPU 容差内一致；schema 不符拒绝；损坏文件拒绝；写入中断保留旧完整文件；评测不写 optimizer/model。
- [ ] `python3 -m unittest discover -s tests -p 'test_rl_ppo.py' -v` 和 checkpoint 测试 RED → 实现 → GREEN；检查有限 loss/grad 和实际参数变化。
- [ ] H100 上先 FP32，再 BF16 autocast smoke：无 NaN/Inf、mask 不变、误差在预先定义的测试容差内；记录 torch/runtime/GPU 和峰值显存。
- [ ] 只声明 learner 正确性，不把 fixture loss 下降或 GPU 可用写成真实游戏学习成功；commit。

### Task 6: 宏动作 PPO 真实游戏闭环（G4）

**Files:** Create `starforge/rl/{train,evaluate}.py`, `tests/test_rl_training.py`;
Modify `starforge/__main__.py`, config、manifest、metrics、README。

**Interfaces:** `train_run(config_path: Path) -> RunSummary`, `evaluate_run(config_path: Path) -> RunSummary`；
新增 `python3 -m starforge train-ppo --config <toml>` / `evaluate --config <toml>`。
训练 config 必须有 `max_updates` 或 `max_wall_seconds`；默认示例 max_updates=10，非无限循环。

- [ ] fixture 验证冻结 θ_k→采样→更新→发布 θ_k+1 顺序；版本混杂直接拒绝，resume 新 episode，配置无运行上限拒绝。
- [ ] 组合 Task 2–5，先对内置 AI/固定规则基线，terminal-only reward；真实 collect 一批、update 一次、保存并重载再继续一次。
- [ ] 用冻结 snapshot 做独立评测；manifest 区分 baseline/synthetic/broodwar、策略和动作 schema、timing、地图 hash、对手 hash/不可验证标签。
- [ ] 在 config 固定 train/eval 地图清单，集合不相交；建立随机/规则/学习策略同规则对照。评测无更新、hidden 归零，不读取训练 RNG 流。
- [ ] `python3 -m unittest discover -s tests -p 'test_rl_training.py' -v` GREEN；真实日志证明参数更新来自真实轨迹，检查失败命令和奖励。
- [ ] 有界 1 小时稳定性运行：队列/内存不持续增长、checkpoint 可恢复、错误率明示；无正向能力进展也如实记录，不保证 PPO 已能学会整局。
- [ ] 更新 G4、训练命令文档和交接；commit。

### Task 7: 实体/空间观测、条件动作与 recurrent PPO（G5）

**Files:** Create `starforge/rl/{features,actions}.py`, `docs/entity-schema-v1.md`,
`tests/test_rl_entities.py`, `tests/test_rl_recurrent.py`, `configs/ppo-entity.toml`;
Modify models、collector、checkpoint、native bridge/v2。

**Interfaces:** `encode_entities(obs: ObservationV2) -> EntityBatch`；
`EntityActorCritic.forward(batch: EntityBatch, hidden, reset_mask) -> PolicyOutput`；
`ConditionalActionDistribution.log_prob(action) -> Tensor`（仅实际激活分支相加）。

- [ ] 先冻结 entity schema：初始人族 SCV/Marine/CC/Barracks/Depot，动作包括 wait、选己方可控单位后的 move/attack/gather/train/build；
  type/vocabulary 表来自固定 BWAPI 枚举映射并入 manifest。支持范围外命令 mask 掉，明确仍是有限单位/科技的混合 agent。
- [ ] 起步 max_entities=512；稳定按身份排序，own/currently-visible-enemy/visible-neutral 分组；
  每实体包含 id、owner relation、type、position、HP/shield/energy、completion、可观测 command 状态。
  地图用最多 128×128 build tiles 的 buildable/walkable/visible/explored 层；位置统一 pixels，
  tile 转换集中处理。具体归一化、特征列、单位 ID 重用规则写入 schema 后测试，不凭随机 dict 顺序编码。
- [ ] 超过实体/地图容量明确报 unsupported，终止该样本并统计，不静默裁切或伪造 loss；未来扩容须变更 schema。
  hidden enemy 字段不得借助全知接口补齐；消失/死亡区分，死亡确认来自合法事件。
- [ ] 测试迷雾过滤、padding、同单位稳定映射、空合法参数分支、条件 joint logprob、动作失效保留采样身份；fixture RED 后实现 native 与 Python 编码。
- [ ] 建议网络：unit encoder 4 层 width384/6 heads Transformer，空间 CNN，融合 GRU512，条件动作头和值头；报告实际参数量（目标约 5–20M，不为凑数扩模型）。
- [ ] 依设计 §6 实现 rollout256/训练片段64/burn-in最多16、episode 和版本屏障 reset；测试多玩家 hidden 隔离、无跨局 trace、burn-in 无 loss、padding 无梯度贡献。
- [ ] 加边界数值测试：定期 reset 的非终局尾部以 θ_k + 零 hidden bootstrap；普通时间限制或
  故障切断使用最后可信持续 hidden，真终局为零。burn-in 从前缀起点保存的 hidden 开始，
  测试不能拿 loss 片段起点 hidden 再重放前缀。
- [ ] `python3 -m unittest discover -s tests -p 'test_rl_entities.py' -v` / `test_rl_recurrent.py` GREEN；真实检查采矿/移动/攻击/建造命令及执行帧。
- [ ] 冻结一份宏 PPO 和实体 PPO 各自评测；不同动作权限不能把胜率差直接归因于网络。记录保留规则和未支持单位/科技，更新 G5/commit。

### Task 8: 最新策略双边自博弈与有界长跑（G6）

**Files:** Modify scheduler、runner、collector、train；Create `configs/selfplay.toml`,
`tests/test_rl_selfplay.py`, `docs/selfplay.md`。

**Interfaces:** `SelfPlayAssignment(match: MatchSpec, policy_version: int)`：双方版本相同；
`reconcile_results(left, right) -> MatchResult`：只输出一份比赛结果，保留双方轨迹引用。

- [ ] 先写双端 win/loss 对应、结果冲突、同一版本、更新屏障、对局早结束、单方故障、用户中断恢复测试。
- [ ] 实现双方 trajectory 采集、episode/policy 同步、reset 和 match 级结果；奖励符号与双方视角一致。
  不加入历史池，终局奖励默认零和；任何新增 shaping 先版本化公式及可观测输入。
- [ ] 测试 GREEN；真实双方 agent 完成至少 20 场配对自博弈，有回放、双方记录核对及错误统计。
- [ ] 先小规模 profile；使用当前已证明稳定的 worker 档位，在用户指定或明确有界预算内运行，记录时长/样本量/学习与冻结评测曲线。
- [ ] 实测 CTRL-C/worker crash/低磁盘空间：有序停止、保存可恢复 checkpoint，只终止自己的进程。
- [ ] GPU 利用率低时先 profile 环境等待，再决定 batching/并发；不要直接开启异步 PPO 或改成大网络。更新 G6/commit。

### Task 9: 固定 Pluto 的评测与正式交接（G7）

**Files:** Create `configs/eval-pluto.toml`, `docs/benchmark-pluto.md`,
`tests/test_runtime_evaluation.py`; Modify evaluate、manifest、metrics、交接文档。

**Interfaces:** `BenchmarkSpec` 固定 model/DLL/map SHA256、双方种族、出生位置安排、
timing/规则、cold-start bandit profile 和 game seed 能否控制；对手未知身份不得写为已验证。

- [ ] 准备官方 Pluto release，核验 AVX2 可用；先跑官方 bench 并限制 CPU 线程，再做少量兼容性对局。
- [ ] 隔离每个并发实例及 bandit 写目录；测试模型文件在评测中被替换时仍引用已加载快照 hash，cold-start 统计不串局。
- [ ] 调度按地图/matchup/出生位置平衡；控制不了的游戏 seed 写 null；禁止宣称严格复现随机游戏状态。
- [ ] pilot 后才扩大到每 matchup 至少 200 局的正式评测；预先固定数量/规则，报告 wins/losses/draws/errors/truncations、完成局胜率、Wilson 区间与相关样本限制。
- [ ] error/truncation 不进完成局胜率分母，但独立报告比例；两玩家数据不当两场；replay 与 manifest 可追溯。
- [ ] 发布实际证据和未完成项；初期输给 Pluto 不阻止工程验收，不能用对弱对手或 synthetic 的成绩代替。
- [ ] 更新 docs/handoff-h100.md、docs/validation.md、README 和计划勾选；commit。更强策略/三族/长记忆/历史池另写实验计划。

## 计划自审与接续规则

- G0–G7 对应 Task 0–9；所有真实游戏门槛明确独立于 fixture 测试。
- 当前 31 测试的旧基线只作为起点，不限制未来测试数量；文档任务本身不要求重复跑训练。
- config/example 命令在所属任务完成前不可作为“已存在功能”引用。
- 每任务结束记录实际命令及结果；Git checkout 可做一任务一 commit，未初始化仓库时不要伪造 commit。
- 硬件/资产阻塞不授权跳过验证或编造 launcher 参数；能独立推进的部分先完成，注明仍待哪一个 gate。
- 不预先复制游戏资源到源码仓库；迁移入口和首次会话提示见 `docs/handoff-h100.md`。
