import unittest

from server import build_status_payload


class ServerStatusPayloadTest(unittest.TestCase):
    def test_status_payload_includes_connect_targets_and_phone_command(self):
        payload = build_status_payload(
            host="10.0.0.24",
            http_port=8080,
            websocket_port=8765,
            ip_candidates=["10.0.0.24", "127.0.0.1"],
        )

        self.assertEqual(payload["type"], "status")
        self.assertEqual(payload["dashboard_url"], "http://10.0.0.24:8080")
        self.assertEqual(payload["phone_ws_url"], "ws://10.0.0.24:8765/phone")
        self.assertEqual(
            payload["phone_command"],
            "python phone_client.py --server 10.0.0.24",
        )
        self.assertEqual(payload["ip_candidates"], ["10.0.0.24", "127.0.0.1"])

    def test_status_payload_uses_first_candidate_when_host_is_not_provided(self):
        payload = build_status_payload(
            host=None,
            http_port=8080,
            websocket_port=8765,
            ip_candidates=["192.168.1.15"],
        )

        self.assertEqual(payload["host"], "192.168.1.15")
        self.assertEqual(payload["dashboard_url"], "http://192.168.1.15:8080")


if __name__ == "__main__":
    unittest.main()
