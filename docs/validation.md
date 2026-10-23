# Validation record — 2026-10-22

## Route 1 / Task 1 prerequisites — 2026-10-23

Status: environment smoke, MSVC build and Wine module probes passed on the
user-approved independent `native/wine-route1` branch. **No real game has run.**

- User confirmed no game resource is installed/provided, authorized trying the
  official free download and authorized an independent Windows build branch.
- Verified the Blizzard 1.18 announcement says the classic game is free. Its
  linked PC installer request succeeded (HTTP 200) but resolved to current
  `Battle.net-Setup.exe`, product 2.0.0.4232, 4,700,880 bytes, SHA256
  `f4643a2086c0cecb1ab68cc601bf38c1a0a6f7ef5914ad03375cc9449385bec6`.
  This is not a 1.16.1 installation; no compatible game asset or replay is claimed.
- Installed Wine 9.0~repack-4build3 for amd64/i386, Xvfb
  2:21.1.12-1ubuntu1.9, xauth/X11 query tools, CMake 3.28.3 and 7-Zip 23.01.
  Enabled i386; seven matching multiarch runtime dependencies required patch
  updates, no GPU/kernel updates or package removals. NVIDIA driver still 615.71.10.
  Slow Azure HTTP downloads were resolved using an operation-local official Ubuntu
  HTTPS source list, not by disabling signatures or changing system repositories.
- Xvfb `xdpyinfo` returned a responsive 1024x768 display. A disposable win64 Wine
  prefix executed the actual PE32+ x64 and PE32 x86 cmd binaries, both exact
  success markers/exit 0, then showed a Win32 Notepad window. Owned process PIDs
  were stopped and the prefix removed. Bootstrap COM/RpcSs/initial-directory
  errors were retained; this limited probe is not a full runtime/game validation.
- Local evidence: `runs/route1-20261023T083536Z/{host.json,packages.txt,assets.json}`,
  `wine-probe/{result.json,wineboot.log,windows.txt}`, and the dependency plan.
  Downloads/SDK are outside Git, indexed by the ignored assets manifest.
- Official BWAPI 4.4.0 archive SHA256:
  `e6d1abeff2a9b31886d9ade15c5c783a32f7e973f1f0e7137911f3d083fa72e2`.
  Its PE32 runtime DLL SHA256:
  `f2e0f937e9592157656118fa7e5ff30c2327694ed56c1d8f55687972ad97d308`.
  Runtime imports include Storm.dll, MSVCP140.dll and VCRUNTIME140.dll.
- Archive inspection confirmed matching headers, BWAPILIB and example source, but
  **no** BWAPILIB.lib/BWAPI.lib or ExampleAIModule.dll. Corrected the CMake library
  input and added pinned MSVC build/PE/exports/module-lifetime probes. No Linux
  cross-compiler or relaxed ABI guard was used.
- Native implementation commit `287aee0` passed the
  [Windows build](https://github.com/wukong121/StarForge/actions/runs/39926874158)
  and [Python CI matrix](https://github.com/wukong121/StarForge/actions/runs/39926873851).
  MSVC tools 14.44.35207 built Release/Win32 BWAPILIB, official example, StarForge
  and the probe. Exact exports/PE32 checks, both module lifetimes and three
  negative probe cases passed on Windows.
- Downloaded artifact ID `12489358524`, archive SHA256
  `c4d7e9b108c8f752c4e2d2a14bbea5aa37cdc429f39ce27a5d90ddea715688cc`,
  matching GitHub metadata. Verified source revision and every manifest file hash.
  StarForge.dll:
  `979ceeb2e18e92b04f1c5859ba68f0041260dc4590225c4f4131d1f60fb18126`;
  ExampleAIModule.dll:
  `8fda4ca407d1995b5702dafb19aa6b02896ee888bbfc2f3a8cdbf0cbe3ab38dc`.
- On this H100 host, a new isolated Wine prefix successfully loaded **both**
  MSVC-built modules, resolved exact entry points, called `gameInit(nullptr)`,
  created/destroyed AIModule objects, and unloaded. Expected exit codes for
  missing argument/file/entry points were 1/2/3. No game callbacks or game
  process were involved. Wine builtin CRT was sufficient for this probe;
  no native VC runtime or game compatibility is thereby certified.
  Evidence: `runs/route1-20261023T083536Z/native-wine/result.json`,
  associated logs and `native-build-manifest.json`. Owned server PID was stopped
  and the disposable prefix removed.
  PE inspection, Windows/Wine loading and real BWAPI loading are separate gates.
- Before that push: `python3 -S -m unittest discover -s tests -v` → **53 passed
  in 1.826 seconds**; whitespace check passed. Unrelated user editor files were
  not staged.

G1 remains blocked by a legally available 1.16.1 game directory, actual injection,
commands and replay. Neither the downloaded Battle.net launcher nor native
loader-probe success can satisfy it.

## Linux Task 0 — 2026-10-23

This section is direct evidence from the Linux checkout, superseding the older
Windows-only baseline for the commands listed here. No real game or GPU training
was run. The source checkout began at `4027240`; Task 0 implementation is committed
as `8299994`.

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
gates remain unverified.

### Publication preflight — 2026-10-23

- User explicitly authorized committing and pushing this milestone, then confirmed
  reuse of the existing commit author. Set only repository-local Git author fields.
- Fresh lockfile, Ruff/format and strict mypy checks passed; all 53 stdlib tests
  passed again in 1.818 seconds.
- Committed the 14 verified milestone files as `8299994`; ignored environments,
  tools, build outputs, host evidence and run data were not staged.
- SSH `ls-remote` succeeded; before publication remote main matched local baseline
  `4027240`. Origin fetch and push both use the user-specified SSH repository URL.
  Publication must use a normal push and be checked against actual remote refs.

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
