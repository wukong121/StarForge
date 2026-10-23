# StarForge — agent handoff

## Start here

Read these files in order before implementation:

1. `docs/handoff-h100.md` — current state, first commands, next deliverable.
2. `docs/superpowers/specs/2026-10-23-h100-architecture-design.md` — architecture and correctness contracts.
3. `docs/superpowers/plans/2026-10-23-h100-development.md` — ordered tasks and acceptance gates.
4. `docs/validation.md` and the source files for the task you are implementing.

The 2026-10-23 H100 design supersedes the older roadmap for future work. The older
protocol v1 and implemented baseline remain supported until explicitly migrated.
The user requested documentation/handoff in the Windows session; implementation is
to continue on their existing Linux H100 host when they ask the next agent to proceed.

User-specified GitHub remote: `git@github.com:wukong121/StarForge.git`.
Origin is configured with that SSH fetch URL and an HTTPS push URL for the same repository,
because this Windows host failed SSH public-key authentication. HTTPS remote inspection on
2026-10-23 found no branches; the initial publication branch is main. Earlier approval-service
failures were resolved. Inspect actual Git log/status and remote refs for publication state;
do not overwrite remote history. The H100 host needs its own GitHub authentication.

## Work rules

- Follow the first unfinished task, record commands/results, then continue when its gate passes.
  Make routine implementation choices yourself and document them; ask only for missing
  external assets/access or a material change of scope. An unavailable game does not
  prevent independent protocol, runner-fixture or learner correctness work.
- Keep current standard-library CLI/tests working. PyTorch belongs in an optional training extra.
- `synthetic` results are fixtures, never StarCraft skill evidence. Keep backend,
  policy family, observation/action schema and timing profiles in artifact metadata.
- No real game or native build has been validated in this checkout. Recheck on the target host.
- Do not assume a Linux compiler can link the MSVC BWAPI SDK into a compatible bot DLL.
  Verify PE32/i386, exported entry points, C++ ABI/runtime and actual BWAPI loading.
- Game observations must respect fog of war. Terminal wins/losses, time limits and
  infrastructure errors are separate. Evaluation must not update policy weights.
- Never silently turn an illegal/stale action into another action in PPO records.
- Use repository-relative paths in portable docs/configs; runtime assets live outside Git.
  Do not commit game MPQs, SDK/runtime binaries, Pluto weights, Wine prefixes, credentials or runs.
- Do not invent an SSH host, remote URL, download location, game launcher command or
  successful cloud test. The user's pasted hardware inventory is evidence of hardware,
  not proof that we accessed it.
- Pluto PPO/reward details are second-hand reports pending original-source verification.
  Our hyperparameters and architecture choices are StarForge decisions, not a reproduction claim.

## Verification

Existing baseline on Linux, from repository root:

```bash
python3 -m starforge doctor
python3 -m unittest discover -s tests -v
python3 -m starforge smoke --out "runs/handoff-$(date -u +%Y%m%dT%H%M%SZ)"
```

Use Python >=3.11. Prefer an isolated `.venv` when installing dependencies. The last
recorded Windows baseline was 31 passing tests; this is not a Linux verification result.
Update `docs/handoff-h100.md` with the next task and `docs/validation.md` with dated
evidence after each milestone. Mark plan checkboxes only when their stated checks passed.
