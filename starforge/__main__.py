"""Commands intentionally work without installing this package."""

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import socket
import sys

from .agent import QLearner
from .doctor import diagnose
from .metrics import append_record, checkpoint_hash, read_records, summarize
from .server import serve_connection
from .training import evaluate_synthetic, train_synthetic


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def parser():
    root = argparse.ArgumentParser(description="StarForge RL foundation (synthetic smoke != StarCraft strength)")
    commands = root.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="read-only platform and game-file diagnostics")
    doctor.add_argument("--starcraft-dir")
    smoke = commands.add_parser("smoke", help="train/evaluate the synthetic integration fixture")
    smoke.add_argument("--episodes", type=positive_int, default=4000)
    smoke.add_argument("--eval-episodes", type=positive_int, default=200)
    smoke.add_argument("--seed", type=int, default=11)
    smoke.add_argument("--out", type=Path)
    report = commands.add_parser("report", help="summarize JSONL by benchmark provenance")
    report.add_argument("path", type=Path)
    serve = commands.add_parser("serve", help="listen for a BWAPI bridge on loopback")
    serve.add_argument("--checkpoint", type=Path, default=Path("runs/broodwar/checkpoint.json"))
    serve.add_argument("--log", type=Path, default=Path("runs/broodwar/matches.jsonl"))
    serve.add_argument("--mode", choices=("train", "eval"), default="train")
    serve.add_argument("--episodes", type=positive_int, default=1)
    serve.add_argument("--port", type=positive_int, default=8765)
    serve.add_argument("--timeout", type=positive_float, default=30)
    serve.add_argument("--max-frames", type=positive_int, default=43200)
    serve.add_argument("--opponent", default="unverified")
    serve.add_argument("--opponent-version", default="unverified")
    serve.add_argument("--seed", type=int, default=11)
    return root


def run(args):
    if args.command == "doctor":
        return diagnose(args.starcraft_dir)
    if args.command == "report":
        return summarize(read_records(args.path))
    if args.command == "smoke":
        if args.seed < 0:
            raise ValueError("seed must be nonnegative")
        output = args.out or Path("runs") / datetime.now().strftime("smoke-%Y%m%d-%H%M%S-%f")
        if output.exists() and any(output.iterdir()):
            raise ValueError("output directory is not empty; choose a new --out directory")
        output.mkdir(parents=True, exist_ok=True)
        checkpoint = output / "checkpoint.json"
        train_synthetic(episodes=args.episodes, seed=args.seed, checkpoint=checkpoint)
        agent = QLearner.load(checkpoint, backend="synthetic")
        held_out_seed = args.seed + args.episodes + 100000
        records = evaluate_synthetic(agent, episodes=args.eval_episodes, seed=held_out_seed,
                                     checkpoint=checkpoint_hash(checkpoint))
        records += evaluate_synthetic(agent, episodes=args.eval_episodes, seed=held_out_seed, random_policy=True)
        for record in records:
            append_record(output / "matches.jsonl", record)
        report = summarize(records)
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output / "config.json").write_text(json.dumps(dict(backend="synthetic", seed=args.seed,
            episodes=args.episodes, eval_episodes=args.eval_episodes, eval_seed=held_out_seed,
            warning="Synthetic fixture only; no evidence of Brood War playing strength."), indent=2), encoding="utf-8")
        return dict(output=str(output.resolve()), report=report)
    if not 1 <= args.port <= 65535:
        raise ValueError("port must be in [1, 65535]")
    training = args.mode == "train"
    if args.checkpoint.exists():
        agent = QLearner.load(args.checkpoint, backend="broodwar")
    elif training:
        agent = QLearner(seed=args.seed, backend="broodwar")
    else:
        raise ValueError("evaluation checkpoint does not exist; train a broodwar checkpoint first")
    if args.checkpoint.resolve() == args.log.resolve():
        raise ValueError("checkpoint and match log must be different files")
    if training and agent.checkpoint_digest is None:
        agent.save(args.checkpoint)
    records = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", args.port))
        listener.listen(1)
        listener.settimeout(args.timeout)
        print(f"Listening on 127.0.0.1:{args.port}; start the BWAPI game bridge.", file=sys.stderr, flush=True)
        for _ in range(args.episodes):
            metadata = dict(opponent=args.opponent, opponent_version=args.opponent_version,
                            checkpoint=agent.checkpoint_digest)
            connection, _ = listener.accept()
            with connection:
                record = serve_connection(connection, agent, training=training, metadata=metadata,
                                          timeout=args.timeout, max_frames=args.max_frames)
            if training:
                agent.save(args.checkpoint)
            append_record(args.log, record)
            records.append(record)
            print(json.dumps(record), file=sys.stderr, flush=True)
    return summarize(records)


def main():
    cli = parser()
    args = cli.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        print(f"starforge: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("starforge: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
