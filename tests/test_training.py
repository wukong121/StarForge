import copy
from pathlib import Path
import random
import tempfile
import unittest

from starforge.agent import QLearner
from starforge.metrics import summarize
from starforge.synthetic import SyntheticEnv
from starforge.training import evaluate_synthetic, train_synthetic


def record(outcome, **changes):
    data = dict(backend="synthetic", map_name="fixture-v1", opponent="fixture",
                opponent_version="1", checkpoint="abc", mode="eval", outcome=outcome)
    data.update(changes)
    return data


class MetricsTests(unittest.TestCase):
    def test_counts_and_interval_exclude_failed_games(self):
        report = summarize([record(x) for x in ["win", "win", "loss", "draw", "error", "truncated"]])[0]
        self.assertEqual(report["completed"], 4)
        self.assertEqual(report["wins"], 2)
        self.assertEqual(report["errors"], 1)
        self.assertEqual(report["truncations"], 1)
        self.assertEqual(report["win_rate"], 0.5)
        self.assertAlmostEqual(report["win_rate_ci95"][0], 0.150039, places=5)
        self.assertAlmostEqual(report["win_rate_ci95"][1], 0.849961, places=5)

    def test_unplayed_and_mixed_results_cannot_be_misrepresented(self):
        self.assertEqual(summarize([]), [])
        report = summarize([record("error")])[0]
        self.assertIsNone(report["win_rate"])
        self.assertIsNone(report["win_rate_ci95"])
        mixed = [record("win"), record("win", backend="broodwar"),
                 record("loss", opponent_version="2"), record("loss", checkpoint="def"),
                 record("loss", mode="train")]
        self.assertEqual(len(summarize(mixed)), 5)
        with self.assertRaises(ValueError):
            summarize([record("victory")])


class SyntheticTests(unittest.TestCase):
    def test_seeded_trajectory_and_action_validation(self):
        a, b = SyntheticEnv(), SyntheticEnv()
        left, right = a.reset(7), b.reset(7)
        rng = random.Random(3)
        while not left.terminal:
            self.assertEqual(left, right)
            action = rng.choice(left.legal_actions)
            left, right = a.step(action), b.step(action)
        self.assertEqual(left, right)
        with self.assertRaises(ValueError):
            a.step(0)
        a.reset(1)
        with self.assertRaises(ValueError):
            a.step(4)

    def test_training_improves_held_out_fixture_and_round_trips(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.json"
            train_synthetic(episodes=4000, seed=11, checkpoint=path)
            learner = QLearner.load(path, backend="synthetic")
            self.assertGreater(learner.updates, 4000)
            before = copy.deepcopy(learner.q)
            learned = evaluate_synthetic(learner, episodes=200, seed=100000)
            baseline = evaluate_synthetic(QLearner(seed=11), episodes=200, seed=100000, random_policy=True)
            learned_wins = sum(r["outcome"] == "win" for r in learned)
            baseline_wins = sum(r["outcome"] == "win" for r in baseline)
            self.assertGreater(learned_wins, baseline_wins + 40)
            self.assertEqual(learner.q, before)
            self.assertTrue(all(r["backend"] == "synthetic" for r in learned))
            fresh = QLearner.load(path, backend="synthetic")
            replay = evaluate_synthetic(fresh, episodes=200, seed=100000)
            self.assertEqual([r["outcome"] for r in learned], [r["outcome"] for r in replay])

    def test_zero_episode_requests_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_synthetic(QLearner(), episodes=0, seed=1)


if __name__ == "__main__":
    unittest.main()
