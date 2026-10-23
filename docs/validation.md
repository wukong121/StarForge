# Validation record — 2026-10-22

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
