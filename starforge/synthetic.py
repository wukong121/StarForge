"""A tiny economic decision fixture. This is NOT a StarCraft simulator."""

import random

from .protocol import Observation


class SyntheticEnv:
    def reset(self, seed: int) -> Observation:
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        self.turn = 0
        self.minerals, self.workers, self.marines = 100, 4, 0
        self.supply, self.barracks = 20, 0
        self.enemy = random.Random(seed).choice((2, 3, 4))
        self.outcome = None
        return self._observation()

    def _observation(self) -> Observation:
        legal = []
        used = 2 * (self.workers + self.marines)
        if self.outcome is None:
            legal = [0]
            if self.minerals >= 50 and used + 2 <= self.supply and self.workers < 10:
                legal.append(1)
            if self.minerals >= 100 and self.supply < 52:
                legal.append(2)
            if self.minerals >= 150 and self.barracks < 2:
                legal.append(3)
            if self.minerals >= 50 and self.barracks and used + 2 <= self.supply:
                legal.append(4)
            if self.marines:
                legal.append(5)
        return Observation(1, self.turn, self.turn * 24, self.minerals, 0, used, self.supply,
                           self.workers, self.marines, self.barracks, 1, self.enemy,
                           tuple(legal), self.outcome is not None, self.outcome,
                           "synthetic-economy-v1", "synthetic")

    def step(self, action: int) -> Observation:
        if not hasattr(self, "outcome"):
            raise ValueError("reset before stepping")
        previous = self._observation()
        if previous.terminal or type(action) is not int or action not in previous.legal_actions:
            raise ValueError("illegal action or episode already ended")
        if action == 1:
            self.minerals -= 50
            self.workers += 1
        elif action == 2:
            self.minerals -= 100
            self.supply += 16
        elif action == 3:
            self.minerals -= 150
            self.barracks += 1
        elif action == 4:
            self.minerals -= 50
            self.marines += 1
        elif action == 5:
            self.outcome = "win" if self.marines >= self.enemy else "loss"
        self.turn += 1
        self.minerals = min(500, self.minerals + self.workers * 8)
        # This is an explicit scripted defeat in the fixture, not an external timeout.
        if self.outcome is None and self.turn >= 24:
            self.outcome = "loss"
        return self._observation()
