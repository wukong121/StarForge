# Linux runtime and development

## Scope

The standard-library baseline works on Python >=3.11. The first Linux milestone
adds read-only host diagnostics and a reproducible development/build workflow.
It does not provide a game launcher, PPO, or real-game validation. Subsequent
MSVC build and Wine module-loading checks are recorded in the route 1 section.

Use the [H100 plan](superpowers/plans/2026-10-23-h100-development.md) for acceptance
order and [validation](validation.md) for dated evidence. Never copy a Windows
virtual environment, game assets, or build directory into the repository.

## Development environment

Use uv **0.13.5**, matching `tool.uv.required-version` and CI. Follow the
[official installation guide](https://docs.astral.sh/uv/getting-started/installation/).
On Ubuntu 24.04 the standalone binary avoids a dependency on system pip or
`ensurepip`; no system Python changes, CUDA installation, or driver update are
needed for this milestone. If curl/CA certificates are missing, an administrator
can prepare them with `sudo apt-get install --no-install-recommends curl ca-certificates`.
Do not run package installation with sudo inside the project environment.

This host's bootstrap placed uv at `.cache/tools/uv` (ignored, not installed
globally). In a fresh shell on this checkout, call that executable directly or
first run `export PATH="$PWD/.cache/tools:$PATH"`. A fresh clone needs its own uv
installation; the binary is not committed.

From the repository root:

```bash
uv sync --locked --python 3.12
uv run --no-sync python -m starforge doctor
uv run --no-sync python -S -m unittest discover -s tests -v
uv run --no-sync python -m starforge smoke --out runs/linux-smoke
```

Choose a fresh smoke output directory on every run. Smoke is a synthetic fixture,
not a StarCraft simulation or evidence of playing strength.

`uv.lock` pins development dependencies and their hashes; `uv sync --locked`
rejects a stale lockfile. Runtime dependencies remain empty. The development group
contains Ruff, mypy, and Hatchling. Hatchling replaces the old setuptools backend;
its build requirement is pinned, and release builds use the backend restored from
the lockfile rather than resolving a new build environment.

For an intentional development dependency update, use `uv lock --upgrade-package
<package>` followed by `uv sync --locked` and the checks below. Updating Hatchling
also requires updating its exact `build-system.requires` pin. Updating uv requires
updating the tool requirement, CI version, and these instructions together.
PyTorch/NumPy belong in a future optional training extra, not core dependencies.

```bash
uv run --no-sync ruff check starforge tests
uv run --no-sync ruff check --extend-select E4,E7,F,I,UP,B starforge/runtime tests/test_runtime_host.py
uv run --no-sync ruff format --check starforge/runtime tests/test_runtime_host.py
uv run --no-sync mypy
uv build --no-build-isolation
```

Legacy files retain a baseline correctness lint; new runtime code has stricter
lint, formatting and strict type checking. This avoids unrelated reformatting.
Extend that stricter scope when adding subsequent packages.

The wheel contains only the Python package and has no runtime dependencies.
CI builds both an sdist and a wheel, installs the wheel without dependencies in an
isolated environment, and runs its CLI outside the checkout. The configured CI
matrix covers Linux/Windows and Python 3.11/3.14; a local Linux pass is not a claim
that the hosted matrix has run. Action revisions are pinned to immutable commits
and workflow permissions are read-only.

The original commands remain supported without uv or third-party packages:

```bash
python3 -m starforge doctor
python3 -m unittest discover -s tests -v
python3 -m starforge smoke --out runs/stdlib-smoke
```

## Diagnostic contract

`doctor` preserves its existing fields and adds `runtime`, with `probe_schema=1`.
Each probe contains `status`, `data`, and a `reason` for unavailable/error evidence:

| Status | Meaning |
|---|---|
| `available` | The specific read/query succeeded, not a compatibility certification |
| `unknown` | A tool/controller/platform is unsupported or unavailable |
| `error` | A read, parse, timeout, or command execution failed; inspect `reason` |

The diagnostic CLI returns JSON even when nested probes fail. A zero exit code
means diagnostic collection completed, not that the host is ready for training.
Automation must inspect the relevant statuses; `real_game_validated` remains false.

- Linux release, logical CPU count/affinity, physical RAM and current-directory
  disk capacity are reported without modifying the host.
- cgroup v2 membership and mount root are resolved from procfs. CPU/memory limits
  are minimized across the visible hierarchy, then combined with CPU affinity and
  physical RAM. Fractional CPU quotas are preserved. `null` limits mean no finite
  limit was found **only when that controller's status is `available`**.
- Bounds are resource ceilings, not performance promises. Hidden ancestors outside
  the mounted namespace cannot be certified. cgroup v1 and non-Linux memory/cgroup
  probes are explicitly `unknown`, not assumed unlimited.
- `nvidia-smi`, `wine`, `Xvfb`, and `cmake` use explicit argument vectors, no shell,
  and a 3-second timeout per command. Returned stdout/stderr are limited to 8,192
  characters per stream, with truncation marked. There are at most four commands.
- Xvfb is queried with `-help`, which does not start a display server. This confirms
  executable responsiveness, not its version; `version_status` remains `unknown`.
  Before game validation, record the selected package version and display behavior.
- No torch import or CUDA tensor test is performed. An NVIDIA driver query is not
  proof of an installed toolkit, working PyTorch runtime, or game compatibility.
- Disk persistence is always `unknown` until confirmed from external/provider
  evidence. Mount type and free space do not prove cloud-volume durability.

To retain a portable evidence location (ignored by Git):

```bash
mkdir -p runs/host-check
uv run --no-sync python -m starforge doctor > runs/host-check/host.json
```

Raw output may include local executable/cgroup paths. Keep it outside commits;
record only necessary summaries and repository-relative evidence references.

## Game and long-run prerequisites

### Route 1 progress on 2026-10-23

The user authorized Wine/Xvfb preparation and an independent Windows CI build
branch, not a merge to main. Installed distro Wine 9.0 for both amd64/i386,
Xvfb 21.1.12, X11 query tools, CMake 3.28.3 and 7-Zip. Enabled i386 for Ubuntu
24.04's shared WoW64 packages; this is not a forced win32-only prefix.
There is no WineHQ repository or system apt mirror change.

The default Azure mirror was very slow for package downloads. A temporary,
operation-local source list used the official Ubuntu HTTPS archive, with normal
Ubuntu signature verification. The Wine install added 136 packages and updated
seven matching multiarch runtime dependencies (glib/lzma/zlib and their associated
tools/data); no packages were removed, no GPU/kernel packages were changed, and
no services were restarted. The earlier display/build-tool install added six
packages without upgrades. Driver remains 615.71.10.

For another Ubuntu 24.04 machine, simulate the dependency changes first, including
which installed libraries must match across architectures:

```bash
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get --simulate --no-remove --no-install-recommends install \
  wine wine64 wine32:i386 xvfb xauth x11-utils cmake 7zip
```

Install only after inspecting that plan. Do not blindly run a system upgrade,
install 32-bit NVIDIA drivers, or copy this host's temporary apt configuration.

Actual bounded tests in an isolated, disposable win64 prefix:

- Xvfb answered `xdpyinfo` at 1024x768, without a physical display or TCP listener.
- The prefix's PE32+/AMD64 `system32/cmd.exe` and PE32/i386 `syswow64/cmd.exe`
  both returned their exact expected markers, exit 0.
- A Win32 Notepad window appeared in `xwininfo -root -tree`.
- A foreground persistent wineserver and Notepad were tracked by their own PIDs,
  terminated individually, and the disposable prefix was removed afterward.
- Wine bootstrap logged initial-directory and COM/RpcSs diagnostics. They were
  retained, not interpreted as proof of a clean/fully compatible Windows runtime.
  Console/GUI smoke passed; game rendering, injection and commands remain untested.

Evidence: `runs/route1-20261023T083536Z/` contains host/package data, Wine result
and logs, and an `assets.json` pointing to downloads outside Git. Those outputs
are ignored and contain no real-game result. A cloud temporary volume's data-loss
warning was confirmed; it was not used for assets or modified.

The [official Blizzard free-release announcement](https://news.blizzard.com/en-us/article/20674424/starcraft-brood-war-patch-1-18-patch-notes)
was checked. Its PC download link currently returns **Battle.net Setup
2.0.0.4232**, not an SC1 1.16.1 installation. The official installer was downloaded
and identified, not mistaken for the game or an SDK-compatible executable.
No unofficial game pack, login automation or downgrade was used.

The official BWAPI archive and release source are available outside Git.
It contains no prebuilt `.lib` or example DLL; see [native build](native-build.md)
for the pinned MSVC build, module probe, artifact and licensing details.
That build and the Python CI matrix passed at `287aee0`. Both resulting
PE32/i386 modules then passed the exact-export/object-lifetime probe on this Wine
host, using its builtin CRT, without loading the game or invoking game callbacks.
This is a verified DLL build/load route, not G1 completion.

Before completing Task 1, obtain the actual location of legally usable SC1 **1.16.1** assets
and the BWAPI **4.4.0** SDK/runtime. The game directory has not been supplied in
this checkout; this is not proof that no installation exists elsewhere.

Resolve the MSVC-compatible x86 build route before trying to build the bridge.
Installing GCC/MinGW or removing the CMake platform guard does not prove BWAPI
C++ ABI compatibility. Native PE/exports/runtime checks and actual in-game loading
remain separate acceptance steps.

Wine/Xvfb/CMake were absent at Task 0 and are now installed as recorded above.
Before a real match, use a fresh game prefix and verify the required CRT, game and
injection behavior. Do not force all prefixes to win32, invent a game-launch
command, or change the NVIDIA driver to match the CUDA version displayed by
`nvidia-smi`.

Before storing games, Wine prefixes, checkpoints or replays, the user must choose
an external `STARFORGE_DATA_ROOT` on a volume whose persistence and capacity are
confirmed. Do not format/mount an unused device or start a long run automatically.
The small system volume is suitable for this milestone's lightweight fixtures,
not a default location for training assets.
