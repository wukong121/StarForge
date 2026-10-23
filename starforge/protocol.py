"""Versioned observations. Supply uses BWAPI half-supply units throughout."""

from dataclasses import dataclass, fields

ACTIONS = ("wait", "train_worker", "build_supply", "build_barracks", "train_marine", "attack")
BACKENDS = ("synthetic", "broodwar")
OUTCOMES = ("win", "loss", "draw", "truncated")
PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class Observation:
    protocol: int
    seq: int
    frame: int
    minerals: int
    gas: int
    supply_used: int
    supply_total: int
    workers: int
    marines: int
    barracks: int
    bases: int
    enemy_visible: int
    legal_actions: tuple[int, ...]
    terminal: bool
    outcome: str | None
    map_name: str
    backend: str

    def __post_init__(self):
        for name in ("protocol", "seq", "frame", "minerals", "gas", "supply_used",
                     "supply_total", "workers", "marines", "barracks", "bases", "enemy_visible"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 2**31 - 1:
                raise ValueError(f"{name} must be a nonnegative 32-bit integer")
        if self.protocol != PROTOCOL_VERSION:
            raise ValueError("unsupported observation protocol")
        if type(self.terminal) is not bool:
            raise ValueError("terminal must be a boolean")
        if self.backend not in BACKENDS:
            raise ValueError("unknown backend")
        if not isinstance(self.map_name, str) or not 1 <= len(self.map_name) <= 512:
            raise ValueError("map_name must be a nonempty string of at most 512 characters")
        if self.terminal:
            if self.outcome not in OUTCOMES or self.legal_actions:
                raise ValueError("terminal observations require an outcome and an empty action mask")
        elif self.outcome is not None or not self.legal_actions:
            raise ValueError("nonterminal observations need actions and no outcome")
        if not isinstance(self.legal_actions, tuple):
            raise ValueError("legal_actions must be a tuple")
        if any(type(a) is not int or not 0 <= a < len(ACTIONS) for a in self.legal_actions):
            raise ValueError("invalid action id")
        if len(set(self.legal_actions)) != len(self.legal_actions):
            raise ValueError("duplicate legal action")

    @classmethod
    def from_dict(cls, data: dict) -> "Observation":
        if not isinstance(data, dict) or set(data) != {f.name for f in fields(cls)}:
            raise ValueError("observation fields do not match protocol v1")
        values = dict(data)
        if not isinstance(values["legal_actions"], (list, tuple)):
            raise ValueError("legal_actions must be an array")
        values["legal_actions"] = tuple(values["legal_actions"])
        return cls(**values)

    @property
    def reward(self) -> float:
        if self.outcome == "truncated":
            raise ValueError("truncation is not a game outcome")
        return {None: 0.0, "win": 1.0, "loss": -1.0, "draw": 0.0}[self.outcome]

    def state_key(self) -> str:
        # Coarse baseline only: no memory, terrain, unit identity or strategy history.
        values = (min(self.frame // 240, 20), min(self.minerals // 50, 10),
                  min(self.gas // 50, 10), min(max(self.supply_total - self.supply_used, 0) // 2, 8),
                  min(self.workers // 2, 12), min(self.marines, 20),
                  min(self.barracks, 4), min(self.bases, 4), min(self.enemy_visible, 20))
        return ":".join(map(str, values))
