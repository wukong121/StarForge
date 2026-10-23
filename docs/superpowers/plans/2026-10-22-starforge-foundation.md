# StarForge Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver a runnable, ARM-friendly RL foundation and a BWAPI bridge source suitable for subsequent real-game validation.

**Architecture:** A Python learner communicates with a Win32 BWAPI game module over loopback TCP. A separately labelled synthetic backend validates learning and evaluation without game assets. Terminal rewards and benchmark provenance are explicit.

**Tech Stack:** Python >=3.11 standard library; unittest; C++17, Winsock, BWAPI 4.4.0; CMake.

**Spec:** `docs/superpowers/specs/2026-10-22-starforge-design.md`

## Global Constraints

- No game installation is available. ARM64 Windows is the development host; native-game compatibility is unverified.
- No claim of competitive strength from synthetic data; backend must appear in checkpoints and records.
- Six actions: wait, train_worker, build_supply, build_barracks, train_marine, attack, in this exact wire order.
- BWAPI supply values are doubled; protocol v1, 24-frame decision interval, loopback port 8765.
- Completed outcome reward: win +1, loss -1, draw 0; errors and truncations are separate.
- Python core has no third-party runtime dependency. No automatic game downloads or cloud spending.
- Work directly in the requested empty directory, which has no Git repository. Preserve source and ledger; no worktree/commit scripts until Git exists.
- User authorized planning followed by execution; proceed without another plan approval round.

## Review Focus

- Malformed/non-finite wire or checkpoint numbers, invalid masks → reject with an actionable exception (Task 1).
- Terminal state versus disconnected/truncated session → no fabricated reward or win (Tasks 1, 3).
- ARM OS detected from an emulated x64 process → do not claim x64 hardware compatibility (Task 3).
- Benchmark contamination by backend, checkpoint or opponent version → separate groups; empty sample has no win rate (Task 2).
- Partial/coalesced TCP messages, sequence regressions and timeouts → bounded read and explicit session error (Task 3).

## Task 1: Validated observations and masked learner

**Files:** `pyproject.toml`, `starforge/{__init__,protocol,agent}.py`, `tests/test_core.py`, `.gitignore`.
**Interfaces:** `Observation.from_dict(data)`, `Observation.state_key()`, `QLearner.select(obs, explore=True)`,
`QLearner.update(previous, action, reward, following)`, `save(path)`, `load(path, backend)`.

- [x] Write tests for malformed masks, bool masquerading as integer, terminal reward, masked exploration,
  terminal Q target, checkpoint compatibility and greedy evaluation without learning.
- [x] Run `python -m unittest discover -s tests -v`; confirm missing-module failures before implementing.
- [x] Implement validated immutable observations and tabular Q-learning with atomic JSON saves.
- [x] Run the full tests; expected zero failures.

## Task 2: Synthetic smoke training and reproducible evaluation

**Files:** `starforge/{synthetic,metrics,training}.py`, `tests/test_training.py`.
**Interfaces:** `SyntheticEnv.reset(seed)`, `step(action) -> Observation`,
`train_synthetic(episodes, seed, checkpoint)`, `evaluate_synthetic(agent, episodes, seed)`,
`summarize(records) -> list[dict]`.

- [x] Test identical seeded trajectories, illegal actions, post-terminal steps, real model improvement over random,
  save/reload parity and no evaluation mutation; use held-out seeds for learning comparison.
- [x] Test hand-calculated wins/losses/draws/errors and Wilson interval; mixed backends/opponents/checkpoints stay separate.
- [x] Run tests to observe missing functionality.
- [x] Implement the small synthetic fixture (not an SC1 simulator), training loop and provenance-aware reports.
- [x] Run suite; expected zero failures and a measurable synthetic-policy improvement.

## Task 3: Socket policy service, CLI and diagnostics

**Files:** `starforge/{server,doctor,__main__}.py`, `tests/test_server.py`, `tests/test_cli.py`, `scripts/python.ps1`.
**Interfaces:** `serve_connection(socket, agent, training, metadata, timeout) -> dict`,
CLI commands `doctor`, `smoke`, `serve`, `report`.

- [x] Test real socket streams for fragmented messages, protocol mismatch, frame/sequence regression,
  disconnect and timeout; ensure completed wins differ from session failures and training saves only appropriate state.
- [x] Test subprocess CLI creates checkpoint/JSONL/report, rejects zero episodes, reports OS and process architecture separately.
- [x] Run failing tests, then implement bounded framing, one-episode connections, logging, checkpoint save and loopback listener.
- [x] Run suite and CLI end-to-end; expected smoke artifacts and explicitly unverified game readiness in doctor.

## Task 4: BWAPI bridge source and operational handoff

**Files:** `native/{CMakeLists.txt,StarForge.cpp}`, `README.md`, `docs/{protocol,setup,validation}.md`.
**Interfaces:** C++ module emits protocol v1 observations and accepts `ACT seq id` acknowledgements;
standard `gameInit`/`newAIModule` exports.

- [ ] Verify BWAPI signatures against official headers/docs; restrict all enemy observations to visible units.
- [x] Implement Win32 module source: idle-worker mining, train/build/attack executor, newline framing and timeout diagnostics. Not compiled.
- [x] Attempt configure/build when SDK/toolchain is available; record actual result. Configure failed; SDK/game remain external prerequisites.
- [x] Document PowerShell commands, Python selection, game compatibility gates, benchmark pinning and next milestones.
- [x] Run full suite, smoke CLI and doctor; obtain independent final code review, fix important findings, record evidence. Final suite: 31 passed.

## Execution record

Progress and implementation decisions: `docs/implementation-log.md`. Completion means the checked items only;
native game integration cannot be accepted without a real StarCraft installation.
