"""Masked tabular Q-learning baseline, deliberately independent of ML runtimes."""

import json
import hashlib
import math
import os
from pathlib import Path
import random
import tempfile

from .protocol import ACTIONS, BACKENDS, Observation


def reject_nonfinite_json(token):
    raise ValueError(f"non-finite JSON number: {token}")


def unit_interval(value, name, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    if positive and value == 0:
        raise ValueError(f"{name} must be positive")
    return value


class QLearner:
    def __init__(self, *, seed=0, alpha=0.2, gamma=0.99, epsilon=0.2, backend="synthetic"):
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if backend not in BACKENDS:
            raise ValueError("unknown backend")
        self.alpha = unit_interval(alpha, "alpha", positive=True)
        self.gamma = unit_interval(gamma, "gamma")
        self.epsilon = unit_interval(epsilon, "epsilon")
        self.seed, self.backend = seed, backend
        self.rng = random.Random(seed)
        self.q: dict[str, list[float]] = {}
        self.updates = 0
        self.checkpoint_digest = None

    def select(self, observation: Observation, *, explore=True) -> int:
        if observation.backend != self.backend or observation.terminal:
            raise ValueError("cannot select for terminal observation or wrong backend")
        legal = observation.legal_actions
        if explore and self.rng.random() < self.epsilon:
            return self.rng.choice(legal)
        values = self.q.get(observation.state_key(), [0.0] * len(ACTIONS))
        best = max(values[a] for a in legal)
        return self.rng.choice([a for a in legal if values[a] == best])

    def update(self, previous: Observation, action: int, reward: float, following: Observation):
        if previous.backend != self.backend or following.backend != self.backend:
            raise ValueError("transition backend mismatch")
        if previous.terminal or type(action) is not int or action not in previous.legal_actions:
            raise ValueError("transition starts terminal or uses an illegal action")
        if type(reward) not in (int, float) or not math.isfinite(reward):
            raise ValueError("reward must be finite")
        if following.outcome == "truncated":
            raise ValueError("discard the last transition on external truncation")
        values = self.q.setdefault(previous.state_key(), [0.0] * len(ACTIONS))
        target = reward
        if not following.terminal:
            future = self.q.get(following.state_key(), [0.0] * len(ACTIONS))
            target += self.gamma * max(future[a] for a in following.legal_actions)
        values[action] += self.alpha * (target - values[action])
        self.updates += 1

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = dict(format_version=1, algorithm="tabular_q", actions=list(ACTIONS),
                    backend=self.backend, seed=self.seed, alpha=self.alpha, gamma=self.gamma,
                    epsilon=self.epsilon, updates=self.updates, rng_state=self.rng.getstate(), q=self.q)
        payload = json.dumps(data, allow_nan=False, separators=(",", ":")).encode("utf-8")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                             prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            self.checkpoint_digest = hashlib.sha256(payload).hexdigest()
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    @classmethod
    def load(cls, path, *, backend):
        payload = Path(path).read_bytes()
        data = json.loads(payload.decode("utf-8"), parse_constant=reject_nonfinite_json)
        try:
            if (type(data["format_version"]) is not int or data["format_version"] != 1 or data["algorithm"] != "tabular_q"
                    or data["actions"] != list(ACTIONS) or data["backend"] != backend):
                raise ValueError("incompatible checkpoint version, actions or backend")
            agent = cls(seed=data["seed"], alpha=data["alpha"], gamma=data["gamma"],
                        epsilon=data["epsilon"], backend=backend)
            if type(data["updates"]) is not int or data["updates"] < 0 or not isinstance(data["q"], dict):
                raise ValueError("invalid checkpoint counters or Q table")
            for key, values in data["q"].items():
                if (not isinstance(key, str) or len(key.split(":")) != 9
                        or not all(v.isdecimal() for v in key.split(":"))
                        or not isinstance(values, list) or len(values) != len(ACTIONS)
                        or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
                    raise ValueError("invalid checkpoint Q values")
            state = data["rng_state"]
            if (not isinstance(state, list) or len(state) != 3
                    or type(state[0]) is not int or state[0] != 3
                    or not isinstance(state[1], list) or len(state[1]) != 625
                    or any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in state[1][:-1])
                    or type(state[1][-1]) is not int or not 0 <= state[1][-1] <= 624
                    or (state[2] is not None and (type(state[2]) not in (int, float) or not math.isfinite(state[2])))):
                raise ValueError("invalid checkpoint random state")
            agent.rng.setstate((state[0], tuple(state[1]), state[2]))
            agent.q, agent.updates = data["q"], data["updates"]
            agent.checkpoint_digest = hashlib.sha256(payload).hexdigest()
            return agent
        except (KeyError, TypeError, IndexError, OverflowError) as error:
            raise ValueError("malformed checkpoint") from error
