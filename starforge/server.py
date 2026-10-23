"""One TCP connection per game. Disconnects are errors, never losses."""

from datetime import datetime, timezone
import json
import socket
import time
import uuid

from .protocol import Observation

MAX_MESSAGE = 65536


def serve_connection(connection, agent, *, training, metadata, timeout=30.0, max_frames=43200):
    connection.settimeout(timeout)
    record = dict(backend="broodwar", map_name="unknown", opponent=metadata.get("opponent", "unverified"),
                  opponent_version=metadata.get("opponent_version", "unverified"),
                  checkpoint=metadata.get("checkpoint", "unverified"), mode="train" if training else "eval",
                  outcome="error", seed=None, decisions=0, frames=0, inference_ms=0.0,
                  episode_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc).isoformat())
    previous = None
    last_action = None
    started = time.monotonic()
    try:
        with connection.makefile("rb") as reader:
            while True:
                line = reader.readline(MAX_MESSAGE + 1)
                if not line:
                    raise ValueError("peer disconnected before terminal observation")
                if len(line) > MAX_MESSAGE or not line.endswith(b"\n"):
                    raise ValueError("oversized or incomplete observation")
                observation = Observation.from_dict(json.loads(line))
                if observation.backend != "broodwar" or agent.backend != "broodwar":
                    raise ValueError("game server requires broodwar observations and checkpoint")
                if previous is None:
                    if observation.seq != 0 or observation.terminal:
                        raise ValueError("game must begin with nonterminal sequence 0")
                    record["map_name"] = observation.map_name
                else:
                    if (observation.seq != previous.seq + 1
                            or observation.frame < previous.frame
                            or (not observation.terminal and observation.frame == previous.frame)
                            or observation.map_name != previous.map_name):
                        raise ValueError("sequence, frame or map changed inconsistently")
                record["frames"] = observation.frame
                truncated = observation.outcome == "truncated" or (
                    not observation.terminal and observation.frame >= max_frames)
                if truncated:
                    record["outcome"] = "truncated"
                    try:
                        connection.sendall(f"ACT {observation.seq} -1\n".encode())
                    except OSError:
                        pass
                    break
                if previous is not None and training:
                    agent.update(previous, last_action, observation.reward, observation)
                if observation.terminal:
                    # Receipt of a valid game result is sufficient even if the peer closes before ACK.
                    record["outcome"] = observation.outcome
                    try:
                        connection.sendall(f"ACT {observation.seq} -1\n".encode())
                    except OSError:
                        pass
                    break
                tick = time.perf_counter()
                last_action = agent.select(observation, explore=training)
                record["inference_ms"] += (time.perf_counter() - tick) * 1000
                connection.sendall(f"ACT {observation.seq} {last_action}\n".encode())
                record["decisions"] += 1
                previous = observation
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        record["outcome"] = "error"
        record["error"] = f"{type(error).__name__}: {error}"
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    record["wall_seconds"] = time.monotonic() - started
    return record
