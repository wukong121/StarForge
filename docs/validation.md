# Validation record — 2026-10-22

## Linux Task 0 — 2026-10-23

This section is direct evidence from the Linux checkout, superseding the older
Windows-only baseline for the commands listed here. No real game or GPU training
was run. The source checkout began at `4027240`; Task 0 changes are in the worktree.

### Host and storage

- Ubuntu 24.04.5 LTS, x86-64, kernel 7.0.0-1017-azure; Python 3.12.3.
- 40 online logical CPUs and affinity CPUs; approximately 314.68 GiB RAM, no swap.
  Visible cgroup v2 leaf and ancestors report `cpu.max=max 100000`,
  `memory.max=max`; no additional finite quota found in the visible hierarchy.
- NVIDIA H100 NVL, 95,830 MiB; driver 615.71.10; `nvidia-smi` succeeds.
  CUDA UMD 13.4 is a driver-reported value, not a toolkit/PyTorch verification.
- Workspace system volume: about 29 GiB total, 23 GiB free at initial probe.
  Separate mounted ext4 volumes report about 1,007 GiB total/956 GiB available
  and 126 GiB total/120 GiB available. Another 3.5 TiB device is unmounted.
  No device was modified. Persistence for training data remains **unknown**;
  volume selection/provider confirmation is required before storing large assets
  or starting long runs.
- Wine, Xvfb and CMake were not found on PATH. No game asset path has been supplied.
  GCC presence does not establish an ABI-compatible BWAPI build route.
- Raw host JSON and command output:
  `runs/task0-host-20261023T075145Z/{host.json,host-commands.txt}` (ignored, local only).

### Commands and engineering workflow

- Before changes: `python3 -m unittest discover -s tests -v` → 31 tests passed.
- Baseline `python3 -m starforge smoke --out runs/task0-baseline-20261023T074755Z`
  → 4,000 synthetic training episodes; learned 200/200, random 36/200 on held-out
  seeds. These results are fixtures, **not StarCraft skill evidence**.
- RED: `python3 -m unittest discover -s tests -p 'test_runtime_host.py' -v`
  failed with `ModuleNotFoundError: starforge.runtime` before implementation.
- GREEN: 20 initial host tests passed; full `python3 -S -m unittest discover -s
  tests -v` passed 51 tests after implementation. Two additional portability/error
  regressions are covered in the final verification below.
- Original `python3 -m venv .venv` failed because `ensurepip` was absent; system pip
  and uv were also absent. Resolved without apt/system-Python changes by installing
  the official uv 0.13.5 standalone binary in ignored project-local tooling.
  GitHub release metadata and archive SHA256 were checked:
  `f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f`.
- `uv lock` / `uv sync --locked --python 3.12` succeeded. Locked tools include
  Hatchling 1.32.4, Ruff 0.17.2, mypy 1.20.2. Runtime dependencies remain empty.
- Baseline and stricter scoped Ruff checks, scoped format check and strict mypy
  passed. `python3 -S -m starforge doctor` succeeds without site packages.
- `uv build --no-build-isolation` produced wheel and sdist, building the wheel from
  the sdist. Archive checks confirmed the new runtime/test files, no runtime
  `Requires-Dist`, and no cache/venv/run data in the source distribution.
- Installed the wheel with `uv pip install --no-deps` in an isolated temporary
  environment; `python -I -m starforge doctor` and the installed `starforge smoke
  --episodes 100 --eval-episodes 10` entry point succeeded outside the checkout.
- CI is configured, with immutable action pins, read-only permissions, Linux/
  Windows and Python 3.11/3.14 coverage. It has **not** been run on GitHub here.
- Final verification: `python3 -S -m unittest discover -s tests -v` → **53 tests
  passed in 1.810 seconds**, including 22 host tests. Log:
  `runs/task0-host-20261023T075145Z/tests.log`. Scoped Ruff/format checks, strict mypy
  and `git diff --check` also passed.
- Final locked-environment smoke:
  `runs/task0-final-20261023T075708Z/`; 4,000 training episodes, 200 held-out games
  per policy, learned 200/200 and random 36/200. The checkpoint byte hash matches
  the pre-change baseline:
  `b9c969831618169259d7dfaa64f1111f0b67c251cd2e2d9e802e8d034d176c99`.
  This checks preserved synthetic behavior, not Brood War performance.

### Remaining boundaries

G0's Python/host evidence is available; disk durability remains an explicit
external unknown and blocks long-run storage decisions, not lightweight fixtures.
Native compilation/loading, Wine display behavior, game commands/replays,
automatic match restarts, torch/CUDA tensor operations and all later game/learner
gates remain unverified. No commit was made: the checkout has no configured Git
author name/email; no identity or authentication was invented.

## Publication preflight — 2026-10-23

Latest retry: approval became available; origin setup succeeded using command-scoped trust
for this sandbox-created repository. SSH authentication failed (`Permission denied (publickey)`),
but HTTPS `ls-remote --symref ... HEAD refs/heads/*` exited 0 with no refs. Set the same repository's
HTTPS push URL and selected main for initial publication. Fresh full suite again passed all 31 tests
(6.618 seconds). These updates supersede the earlier publication blocker below; publication itself
must be checked against local and remote commit IDs, not inferred from this preflight.

- User explicitly requested committing and pushing to `git@github.com:wukong121/StarForge.git`.
- Fresh verification: `./scripts/python.ps1 -m unittest discover -s tests -v` exited 0;
  31 tests passed. This remains Windows Python/fixture verification, not native or H100 acceptance.
- Reviewed Git's untracked file list: source, tests, configuration and documentation only;
  build/, runs/, .venv/ and caches remain ignored.
- No initial commit or remote exists yet. Retrying origin setup with explicit user authorization
  was blocked before execution by automatic approval review's invalid `codex-auto-review` model.
  No commit or push was performed; no remote contents were read. Resolve the approval-service
  configuration before continuing Git writes and inspect remote history before publishing.

## Verified locally

- Host: ARM64 Windows 10.0.26300; Python 3.12.14 x64 via Prism; 12 logical CPUs reported.
- Core has no third-party runtime dependencies. Actual socket pairs and CLI subprocesses are exercised.
- Initial full smoke: 4,000 synthetic training episodes, 200 held-out evaluations per policy.
  Learned policy: 200/200; random policy: 36/200. These are fixture results only, not StarCraft results.
- Artifacts: `runs/initial-smoke/checkpoint.json`, `matches.jsonl`, `report.json`, `config.json`.
- Final suite after independent review and regression fixes: `./scripts/python.ps1 -m unittest discover -s tests -v`
  → **31 tests passed**. Includes actual localhost TCP subprocess train/eval sessions with protocol fixtures,
  checkpoint replacement during evaluation, malformed RNG state, and final-ACK failure. These are not real game sessions.
- Three P2 review findings were reproduced and fixed; details in `implementation-log.md`.

## Not verified / remaining prerequisites

- No StarCraft or BWAPI installation; no real matches, no replay validation, no Pluto performance claim.
- Native CMake configure was attempted using installed Visual Studio 18 2026 with `-A Win32`.
  It stopped at compiler discovery: `No CMAKE_CXX_COMPILER could be found.`
  Therefore the bridge has NOT been compiled or run. BWAPI SDK is also absent.
- Direct SDK release-list retrieval was blocked by sandbox networking. An escalation attempt could not
  execute because the automatic approval service returned a configuration error (`Invalid model name ... codex-auto-review`).
  This was an approval-service failure, not an unsafe-action verdict. No workaround download was performed.
- ARM game + injection + Pluto compatibility must be tested independently. Windows AVX2 emulation support
  alone does not establish compatibility or usable training throughput.

## Evidence rules

Keep synthetic and game metrics separate. A passing Python suite does not validate BWAPI ABI, game commands,
compiler/runtime compatibility, real-time behavior, action fairness or competitive strength.
The next acceptance step is the installation/real-game sequence in `setup.md`.
