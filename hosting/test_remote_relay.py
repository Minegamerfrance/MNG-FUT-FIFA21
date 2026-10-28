from pathlib import Path
import socket
import socketserver
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server/runtime-source"))
import remote_relay as relay


class TransportTests(unittest.TestCase):
    def test_only_verified_online_tailnet_device(self):
        status = {"Self": {"Online": True, "TailscaleIPs": ["100.80.0.1"]}, "Peer": {}}
        with patch.object(relay, "tailnet", return_value=status):
            relay.validate_remote("100.80.0.1")
            for host in ("8.8.8.8", "127.0.0.1", "100.80.0.2", "0.0.0.0"):
                with self.assertRaises(ValueError):
                    relay.validate_remote(host)

    def test_tcp_stream_and_half_close(self):
        class Echo(socketserver.BaseRequestHandler):
            def handle(self):
                data = bytearray()
                while True:
                    part = self.request.recv(1024)
                    if not part:
                        break
                    data.extend(part)
                self.request.sendall(data)
        with relay.TCP(("127.77.0.23", 0), Echo) as upstream:
            threading.Thread(target=upstream.serve_forever, daemon=True).start()
            port = upstream.server_address[1]
            servers, stopped = relay.start_relays("127.77.0.23", "127.77.0.22", (port,))
            try:
                payload = bytes(range(256)) * 1024
                with socket.create_connection(("127.77.0.22", port), timeout=3) as client:
                    client.sendall(payload)
                    client.shutdown(socket.SHUT_WR)
                    result = bytearray()
                    while True:
                        part = client.recv(65536)
                        if not part:
                            break
                        result.extend(part)
                self.assertEqual(result, payload)
            finally:
                stopped.set()
                for server in servers:
                    server.shutdown()
                    server.server_close()
                upstream.shutdown()

    def test_udp_reply(self):
        class Echo(socketserver.BaseRequestHandler):
            def handle(self):
                payload, sock = self.request
                sock.sendto(payload, self.client_address)
        with relay.UDP(("127.77.0.23", 17502), Echo) as upstream:
            threading.Thread(target=upstream.serve_forever, daemon=True).start()
            servers, stopped = relay.start_relays("127.77.0.23", "127.77.0.22", (17502,))
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.settimeout(4)
                    client.sendto(b"native-qos", ("127.77.0.22", 17502))
                    self.assertEqual(client.recv(65535), b"native-qos")
            finally:
                stopped.set()
                for server in servers:
                    server.shutdown()
                    server.server_close()
                upstream.shutdown()

    def test_client_cannot_bind_publicly(self):
        with self.assertRaises(ValueError):
            relay.start_relays("127.0.0.1", "0.0.0.0", ())


if __name__ == "__main__":
    unittest.main()
