import copy
import json
from pathlib import Path
import tempfile
import unittest

from starforge.agent import QLearner
from starforge.protocol import ACTIONS, Observation


def obs(**changes):
    data = dict(protocol=1, seq=0, frame=0, minerals=100, gas=0,
                supply_used=8, supply_total=20, workers=4, marines=0,
                barracks=0, bases=1, enemy_visible=0,
                legal_actions=[0, 1, 2, 3], terminal=False, outcome=None,
                map_name="test-map", backend="synthetic")
    data.update(changes)
    return Observation.from_dict(data)


class ProtocolTests(unittest.TestCase):
    def test_invalid_observation_cannot_reach_learner(self):
        for changes in [dict(protocol=2), dict(minerals=-1), dict(seq=True),
                        dict(gas=float("nan")), dict(legal_actions=[]),
                        dict(legal_actions=[0, 6]), dict(legal_actions=[0, 0]),
                        dict(legal_actions=[False]), dict(terminal="false"),
                        dict(outcome="win"), dict(terminal=True),
                        dict(backend="unknown"), dict(map_name="")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                obs(**changes)

    def test_terminal_reward_is_game_result_only(self):
        for outcome, reward in [("win", 1), ("loss", -1), ("draw", 0)]:
            end = obs(terminal=True, outcome=outcome, legal_actions=[])
            self.assertEqual(end.reward, reward)
        self.assertEqual(obs().reward, 0)
        with self.assertRaises(ValueError):
            _ = obs(terminal=True, outcome="truncated", legal_actions=[]).reward

    def test_bwapi_doubled_supply_is_used_for_state_buckets(self):
        a = obs(supply_used=18, supply_total=20)
        b = obs(supply_used=20, supply_total=20)
        self.assertNotEqual(a.state_key(), b.state_key())


class LearnerTests(unittest.TestCase):
    def test_mask_applies_to_exploration_and_greedy_policy(self):
        state = obs(legal_actions=[0, 4])
        agent = QLearner(seed=7, epsilon=1)
        agent.q[state.state_key()] = [0, 100, 100, 100, 2, 100]
        self.assertEqual(agent.select(state, explore=False), 4)
        self.assertEqual({agent.select(state) for _ in range(100)}, {0, 4})

    def test_bellman_target_excludes_illegal_next_actions(self):
        agent = QLearner(alpha=0.5, gamma=0.9)
        before = obs()
        after = obs(seq=1, frame=24, minerals=50, legal_actions=[0, 1])
        agent.q[after.state_key()] = [2, 4, 100, 100, 100, 100]
        agent.update(before, 1, 0, after)
        self.assertAlmostEqual(agent.q[before.state_key()][1], 1.8)

    def test_terminal_target_never_bootstraps(self):
        agent = QLearner(alpha=0.5)
        before = obs()
        end = obs(seq=1, frame=24, minerals=0, terminal=True, outcome="win", legal_actions=[])
        agent.q[end.state_key()] = [100] * len(ACTIONS)
        agent.q[before.state_key()] = [0] * len(ACTIONS)
        agent.update(before, 1, end.reward, end)
        self.assertEqual(agent.q[before.state_key()][1], 0.5)

    def test_evaluation_does_not_insert_unseen_states(self):
        agent = QLearner()
        before = copy.deepcopy(agent.q)
        agent.select(obs(), explore=False)
        self.assertEqual(agent.q, before)
        self.assertEqual(agent.updates, 0)

    def test_checkpoint_round_trip_and_backend_guard(self):
        agent = QLearner(seed=19)
        agent.update(obs(), 1, 1, obs(terminal=True, outcome="win", legal_actions=[]))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "agent.json"
            agent.save(path)
            loaded = QLearner.load(path, backend="synthetic")
            self.assertEqual(agent.q, loaded.q)
            self.assertEqual(agent.updates, loaded.updates)
            self.assertEqual([agent.select(obs()) for _ in range(20)],
                             [loaded.select(obs()) for _ in range(20)])
            with self.assertRaises(ValueError):
                QLearner.load(path, backend="broodwar")
            data = json.loads(path.read_text())
            data["q"][obs().state_key()][0] = float("nan")
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                QLearner.load(path, backend="synthetic")

    def test_rejects_invalid_parameters_and_transitions(self):
        for kwargs in [dict(alpha=0), dict(gamma=1.1), dict(epsilon=-0.1),
                       dict(alpha=float("nan")), dict(seed=True)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                QLearner(**kwargs)
        agent = QLearner()
        with self.assertRaises(ValueError):
            agent.update(obs(), 5, 1, obs())
        with self.assertRaises(ValueError):
            agent.update(obs(), 0, float("inf"), obs())
        with self.assertRaises(ValueError):
            agent.select(obs(terminal=True, outcome="loss", legal_actions=[]))

    def test_invalid_checkpoint_rng_cannot_poison_the_next_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "agent.json"
            QLearner().save(path)
            valid = json.loads(path.read_text())
            invalid = []
            for value in (float("nan"), float("inf"), "not-a-number", True):
                data = copy.deepcopy(valid)
                data["rng_state"][2] = value
                invalid.append(data)
            data = copy.deepcopy(valid)
            data["format_version"] = True
            invalid.append(data)
            for data in invalid:
                with self.subTest(data=data["rng_state"][2], version=data["format_version"]):
                    path.write_text(json.dumps(data))
                    with self.assertRaises(ValueError):
                        QLearner.load(path, backend="synthetic")


if __name__ == "__main__":
    unittest.main()
