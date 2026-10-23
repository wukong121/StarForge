from dataclasses import asdict
import json
import socket
import threading
import unittest

from starforge.agent import QLearner
from starforge.server import serve_connection
from test_core import obs


class ServerTests(unittest.TestCase):
    def exchange(self, payloads, *, training=True, max_frames=43200, fail_final_ack=False):
        server, client = socket.socketpair()
        class FinalAckFailure:
            def __getattr__(self, name):
                return getattr(server, name)

            def sendall(self, data):
                if data.endswith(b" -1\n"):
                    server.shutdown(socket.SHUT_RDWR)
                    raise BrokenPipeError("peer closed before final acknowledgment")
                return server.sendall(data)

        transport = FinalAckFailure() if fail_final_ack else server
        agent = QLearner(backend="broodwar", seed=4)
        result = []
        thread = threading.Thread(target=lambda: result.append(serve_connection(
            transport, agent, training=training,
            metadata=dict(opponent="fixture", opponent_version="1", checkpoint="test"),
            timeout=0.15, max_frames=max_frames)), daemon=True)
        thread.start()
        replies = []
        try:
            client.settimeout(2)
            for parts in payloads:
                for part in parts:
                    client.sendall(part)
                if parts and parts[-1].endswith(b"\n"):
                    replies.append(client.recv(128))
        finally:
            client.close()
            thread.join(3)
            server.close()
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(result), 1)
        return result[0], replies, agent

    def wire(self, **changes):
        return (json.dumps(asdict(obs(backend="broodwar", **changes))) + "\n").encode()

    def test_fragmented_game_updates_only_on_training(self):
        first = self.wire()
        end = self.wire(seq=1, frame=24, terminal=True, outcome="win", legal_actions=[])
        result, replies, agent = self.exchange([[first[:10], first[10:]], [end]])
        self.assertEqual(result["outcome"], "win")
        self.assertEqual(result["decisions"], 1)
        self.assertTrue(replies[0].startswith(b"ACT 0 "))
        self.assertEqual(replies[1], b"ACT 1 -1\n")
        self.assertEqual(agent.updates, 1)
        result, _, agent = self.exchange([[first], [end]], training=False)
        self.assertEqual(result["outcome"], "win")
        self.assertEqual(agent.q, {})
        self.assertEqual(agent.updates, 0)

    def test_disconnect_is_error_not_loss(self):
        result, _, agent = self.exchange([[self.wire()]])
        self.assertEqual(result["outcome"], "error")
        self.assertEqual(agent.updates, 0)

    def test_timeout_is_error_not_draw(self):
        server, client = socket.socketpair()
        try:
            result = serve_connection(server, QLearner(backend="broodwar"), training=True,
                                      metadata={}, timeout=0.01)
        finally:
            server.close()
            client.close()
        self.assertEqual(result["outcome"], "error")

    def test_invalid_sequence_frame_backend_and_json_are_errors(self):
        bad_messages = [self.wire(seq=0, frame=24), self.wire(seq=1, frame=0),
                        self.wire(seq=2, frame=24), b'{"protocol":2}\n', b'[]\n',
                        b'x' * 65537 + b'\n']
        for message in bad_messages:
            with self.subTest(message=message[:80]):
                result, _, agent = self.exchange([[self.wire()], [message]])
                self.assertEqual(result["outcome"], "error")
                self.assertEqual(agent.updates, 0)

    def test_explicit_truncation_does_not_become_reward(self):
        end = self.wire(seq=1, frame=24, terminal=True, outcome="truncated", legal_actions=[])
        result, _, agent = self.exchange([[self.wire()], [end]])
        self.assertEqual(result["outcome"], "truncated")
        self.assertEqual(agent.updates, 0)

    def test_coalesced_observations_preserve_terminal_result(self):
        end = self.wire(seq=1, frame=24, terminal=True, outcome="win", legal_actions=[])
        result, _, agent = self.exchange([[self.wire() + end]])
        self.assertEqual(result["outcome"], "win")
        self.assertEqual(agent.updates, 1)

    def test_server_frame_limit_discards_incomplete_transition(self):
        result, replies, agent = self.exchange([[self.wire()], [self.wire(seq=1, frame=24)]], max_frames=24)
        self.assertEqual(result["outcome"], "truncated")
        self.assertEqual(replies[-1], b"ACT 1 -1\n")
        self.assertEqual(agent.updates, 0)

    def test_truncation_survives_final_ack_failure(self):
        end = self.wire(seq=1, frame=24, terminal=True, outcome="truncated", legal_actions=[])
        result, _, agent = self.exchange([[self.wire()], [end]], fail_final_ack=True)
        self.assertEqual(result["outcome"], "truncated")
        self.assertEqual(agent.updates, 0)


if __name__ == "__main__":
    unittest.main()
