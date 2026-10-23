"""Standalone smoke experiment; no game result is ever produced by this module."""

from datetime import datetime, timezone

from .agent import QLearner
from .synthetic import SyntheticEnv


def check_run(episodes, seed):
    if type(episodes) is not int or episodes <= 0:
        raise ValueError("episodes must be a positive integer")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")


def train_synthetic(*, episodes, seed, checkpoint):
    check_run(episodes, seed)
    agent = QLearner(seed=seed, epsilon=0.3)
    environment = SyntheticEnv()
    for episode in range(episodes):
        observation = environment.reset(seed + episode)
        while not observation.terminal:
            action = agent.select(observation)
            following = environment.step(action)
            agent.update(observation, action, following.reward, following)
            observation = following
    agent.save(checkpoint)
    return agent


def evaluate_synthetic(agent, *, episodes, seed, random_policy=False, checkpoint="in-memory"):
    check_run(episodes, seed)
    if agent.backend != "synthetic":
        raise ValueError("synthetic evaluation requires a synthetic checkpoint")
    records = []
    environment = SyntheticEnv()
    # Evaluation has its own RNG. Even the training RNG is unchanged by evaluation.
    policy = QLearner(seed=seed)
    policy.q = agent.q
    for episode in range(episodes):
        observation = environment.reset(seed + episode)
        while not observation.terminal:
            action = (policy.rng.choice(observation.legal_actions) if random_policy
                      else policy.select(observation, explore=False))
            observation = environment.step(action)
        records.append(dict(backend="synthetic", map_name=observation.map_name,
                            opponent="synthetic-threshold", opponent_version="1",
                            checkpoint="random-policy-v1" if random_policy else checkpoint,
                            mode="eval", outcome=observation.outcome, seed=seed + episode,
                            frames=observation.frame, decisions=observation.seq,
                            timestamp=datetime.now(timezone.utc).isoformat()))
    return records
