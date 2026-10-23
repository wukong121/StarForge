# StarForge wire protocol v1

One TCP connection is one game. The game DLL connects to `127.0.0.1:8765`.
The Python server never launches or resets the game. All observation fields below are required;
unknown fields are rejected so protocol changes must be versioned.

The game sends a UTF-8 JSON object terminated by LF, at most 65,536 bytes including LF:

```json
{"protocol":1,"seq":0,"frame":0,"minerals":50,"gas":0,"supply_used":8,"supply_total":20,"workers":4,"marines":0,"barracks":0,"bases":1,"enemy_visible":0,"legal_actions":[0,1],"terminal":false,"outcome":null,"map_name":"example.scx","backend":"broodwar"}
```

Numeric fields are nonnegative 32-bit integers (booleans are not integers here). Supply is BWAPI's
doubled representation: 2 means one displayed supply. Unit counts include own units under construction;
legal actions use completed, commandable units. Only currently visible enemy units are counted.

| ID | Intent | Executor |
|---|---|---|
| 0 | wait | no macro command |
| 1 | train_worker | one idle Command Center trains an SCV |
| 2 | build_supply | one eligible SCV builds a Supply Depot |
| 3 | build_barracks | one eligible SCV builds Barracks |
| 4 | train_marine | one idle Barracks trains a Marine |
| 5 | attack | Marines attack a visible enemy position or scout public map start locations |

Idle-worker mining runs as a scripted maintenance action. Legal masks are checked when observations
are generated; BWAPI commands can still fail later. The DLL records cumulative execution failures.
Failed commands remain attempted actions in learning; there is no action-failure reward.

Python replies `ACT <seq> <action_id>\n`. The DLL checks the sequence and mask before executing.
Sequence starts at 0 and increments by exactly 1. Nonterminal frames must increase; a terminal frame
may equal the preceding frame. The map is fixed for a connection.

Terminal observation: `terminal=true`, `legal_actions=[]`, and `outcome` is `win`, `loss`, `draw`, or
`truncated`. Python acknowledges with `ACT <seq> -1\n`. A nonterminal `-1` response is an instruction
to end an externally time-limited episode, not a game defeat. The server defaults to a 43,200-frame limit.
The DLL reports loss only when BWAPI confirms defeat; otherwise `onEnd(false)` is conservatively truncated.
The native prototype does not infer draws from a non-winning callback.

Only genuine completed outcomes generate terminal reward: +1 / -1 / 0. Socket errors, malformed data,
timeouts, or EOF before terminal become `error`; no fabricated final transition is learned.
Truncation discards the final incomplete transition. Earlier observed transitions can already have
updated the table in training mode. Evaluation never updates it or saves a new checkpoint.

Logs separate results by backend, map name, opponent label/version, checkpoint hash and train/eval mode.
The checkpoint hash is computed from the exact bytes loaded, then held fixed during evaluation, even if
another process replaces that pathname. Training records use the checkpoint at the start of the episode;
the hash advances after the updated model is saved. A new training service saves its initial model before accepting games.
Win rate is wins / (wins + losses + draws); Wilson 95% bounds describe the binary win indicator.
Errors/truncations are excluded from that denominator and reported separately with failure rate.
Identical seeds or correlated games can violate the interval's independence assumption: use proper
match scheduling before interpreting a real benchmark. Game seed is null because this bridge cannot set it.

Opponent labels are operator claims. The service does not authenticate opponents, validate game binaries,
or provide a tournament referee. Remote deployment requires an existing secure tunnel.
