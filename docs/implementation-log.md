# Execution ledger — StarForge foundation

- 2026-10-23 (Linux Task 0): User authorized implementation and requested modern
  engineering/dependency/packaging practices. Added typed stdlib host diagnostics
  and `doctor.runtime`, resolving visible cgroup v2 ancestor limits and affinity;
  command errors/timeouts remain explicit and never certify game readiness.
  Tests were RED on the missing runtime module, then GREEN. Preserved v1/Q-learning
  behavior and zero runtime dependencies.
- Engineering decision: uv 0.13.5 + committed lockfile, Hatchling wheel/sdist builds,
  scoped Ruff/strict mypy, existing unittest runner, immutable/read-only CI matrix.
  No pytest migration, container/orchestration framework, or torch dependency is
  necessary for this milestone. CI has not run remotely.
- Bootstrap: pip/ensurepip/uv missing. Used a checksum-verified official uv binary
  in ignored local tooling; restored `.venv` with uv, without system package changes.
  Verified the built wheel without dependencies outside the source checkout.
- Linux hardware and synthetic baseline evidence now exists; see validation.md.
  Wine/Xvfb/CMake were not on PATH, game/SDK/build assets were not supplied, storage
  persistence remains unknown. No native build, game, GPU training, remote push,
  device changes or fabricated launcher commands. Git author identity is absent,
  so changes remain uncommitted. Next gate is Task 1 assets/build compatibility.

- 2026-10-23 (approved publication retry): Approval service recovered. Configured origin, retaining
  the user's SSH fetch URL; SSH authentication failed, so configured HTTPS push URL for the same repo.
  HTTPS ls-remote succeeded with no remote branches. Selected main for the initial snapshot and reran
  all 31 tests successfully. Publication status is to be verified against the remote commit after push.

- 2026-10-23 (publish request): User explicitly authorized commit and push. Reviewed candidate files
  and reran all 31 tests successfully. Origin setup was retried through required escalation;
  automatic approval review again failed with invalid model `codex-auto-review` before execution.
  No commit/push occurred; origin and remote history remain unconfigured/unverified. Recorded fresh
  validation evidence; further user confirmation is not the missing prerequisite.

- 2026-10-23 (remote follow-up): User supplied `git@github.com:wukong121/StarForge.git`.
  Local `git init` succeeded. `git remote add origin` failed to lock `.git/config` (permission denied);
  escalation was not executed because automatic approval review failed with invalid model `codex-auto-review`.
  Recorded the URL and clone instructions in the handoff. No origin configuration, commit, push or remote access verified.

- 2026-10-23: User requested plan/handoff only for their existing Linux H100 host (40 visible CPUs,
  314 GiB RAM, H100 NVL). Added root AGENTS.md, H100 handoff, architecture and task plan; updated README.
  No remote host access, package installation, game execution, PPO implementation or GPU training in this session.
  Hardware inventory is user-provided; Linux acceptance remains pending. Local directory is still not a Git repository.
  New roadmap selects synchronous latest-policy self-play initially; historical opponent pools are optional future experiments.
- 2026-10-23: Independent H100 design builder check found two actionable contract ambiguities.
  Resolved paired rollout boundaries with match-level variable-length windows/padding (no per-player fill deadlock),
  and recurrent boundary bootstrap using old weights plus reset hidden when the next window resets memory.
  Explicitly identified burn-in-prefix hidden state. No user clarification required; no runtime validation implied.
- 2026-10-23: Reviewer rechecked the corrected design and task plan; no important open design questions remained.
  Checked all local Markdown links and UTF-8 text in the six touched documentation files; passed.
  This was a documentation-only change: no runtime tests were rerun, and the H100 task checkboxes remain unchecked.

- 2026-10-22: User authorized plan then execution. Empty workspace is not a Git repository.
- Ruling: implement in this requested directory without Git/worktree scripts; source remains directly reviewable. Git history can be initialized later.
- Ruling: use standard-library Q-learning for the first integration baseline; this avoids ARM dependency blockers and is explicitly not the final competitive learner.
- Ruling: no game installation means actual matches and ARM compatibility remain unverified; independent smoke and protocol work can proceed.
- Pre-flight: protocol observations are shared by learner, synthetic fixture and server; action order and backend tags are fixed by the spec.
- Research: direct Pluto README is newer than search snippets (v2.0 / md09b_1331000). Rank not independently verified.
- Design builder check: independent reviewer found no important unanswered implementation questions.
- Task 1: complete. RED: missing core modules; GREEN: 9 tests passed.
- Task 2: complete. RED: missing training/metrics modules; GREEN: 14 tests passed, including held-out policy improvement.
- Task 3: implemented. RED: missing CLI/service; GREEN: 23 tests passed. Real socket pairs, disconnects, malformed messages and timeout covered.
- Native Task 4: source and CMake supplied. Configure attempted; installed VS 2026 Win32 compiler discovery failed. SDK absent, so native compile and runtime acceptance remain pending.
- Debugging: platform.machine/environment report x64 under Prism. IsWow64Process2 reports native ARM64 with UNKNOWN process; PE header is 0x8664. Retain runtime architecture when process code is UNKNOWN. Regression tests added.
- Smoke: 4,000 training / 200 eval episodes; learned 200 wins, random 36 wins, strictly synthetic. Artifacts under runs/initial-smoke.
- External restriction: automatic approval service configuration error prevented official SDK release-list retrieval; no download or bypass performed.
- Task 3: complete after added real TCP subprocess training/eval persistence checks, coalesced-message and frame-limit tests; 28/28 tests pass.
- Final independent review: three P2 findings, no critical findings. All three reproduced with failing regression tests before the fix pass.
- Final: fixed invalid random-state loading (finite/null Gaussian cache, MT state validation and strict version); test_invalid_checkpoint_rng_cannot_poison_the_next_save RED → GREEN.
- Final: fixed evaluation checkpoint provenance race; load hashes the exact bytes read, save hashes the exact bytes persisted, service keeps the in-memory model's digest. test_eval_provenance_stays_with_loaded_model_when_file_is_replaced RED → GREEN.
- Final: fixed truncation ACK failure classification; test_truncation_survives_final_ack_failure RED → GREEN.
- Final verification: `./scripts/python.ps1 -m unittest discover -s tests -v` → 31/31 tests passed, 2026-10-22.
- Final review scope: native compile, actual BWAPI command behavior, ARM game compatibility and playing strength remain unjudged because SDK/game are absent. These require real-game acceptance; static source review is not substituted for it.
- No deferred minor code findings. Foundation Python tasks complete; native source delivery complete, native compile/runtime acceptance pending.
