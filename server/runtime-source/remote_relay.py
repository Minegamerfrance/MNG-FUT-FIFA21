"""Private Tailscale test transport. No club engine or saved club on the client."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import select
import shutil
import socket
import socketserver
import subprocess
import threading
import time

PORTS = (8090, 44321, 10853, 17502, 42232, 8081, 42231)


def tailnet():
    executable = shutil.which("tailscale")
    if not executable and os.name == "nt":
        executable = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tailscale/tailscale.exe")
    if not executable:
        raise RuntimeError("Tailscale is required for the private hosting test")
    result = subprocess.run([executable, "status", "--json"], check=True, capture_output=True,
                            text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    status = json.loads(result.stdout)
    if status.get("BackendState") != "Running":
        raise RuntimeError("Connect Tailscale before starting the hosting test")
    return status


def validate_remote(host):
    address = ipaddress.ip_address(host)
    if address not in ipaddress.ip_network("100.64.0.0/10"):
        raise ValueError("Only a verified Tailscale IPv4 address is accepted")
    status = tailnet()
    devices = [status.get("Self") or {}] + list((status.get("Peer") or {}).values())
    if not any(host in device.get("TailscaleIPs", []) and device.get("Online") for device in devices):
        raise ValueError("The server is not an online device in your Tailscale network")


class TCP(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False


class UDP(socketserver.ThreadingUDPServer):
    daemon_threads = True
    allow_reuse_address = False


def start_relays(remote, bind="127.0.0.1", ports=PORTS):
    if not ipaddress.ip_address(bind).is_loopback:
        raise ValueError("Client relay must bind to loopback")
    capacity = threading.BoundedSemaphore(96)
    stopped = threading.Event()

    class Stream(socketserver.BaseRequestHandler):
        def handle(self):
            if not capacity.acquire(blocking=False):
                return
            try:
                with socket.create_connection((remote, self.server.server_address[1]), timeout=5) as upstream:
                    self.request.settimeout(10)
                    upstream.settimeout(10)
                    readers = [self.request, upstream]
                    while readers and not stopped.is_set():
                        ready, _, _ = select.select(readers, [], [], 1)
                        for source in ready:
                            target = upstream if source is self.request else self.request
                            data = source.recv(65536)
                            if not data:
                                readers.remove(source)
                                try:
                                    target.shutdown(socket.SHUT_WR)
                                except OSError:
                                    pass
                            else:
                                target.sendall(data)
            except OSError:
                pass
            finally:
                capacity.release()

    class Datagram(socketserver.BaseRequestHandler):
        def handle(self):
            if not capacity.acquire(blocking=False):
                return
            try:
                payload, local = self.request
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream:
                    upstream.settimeout(3)
                    upstream.connect((remote, self.server.server_address[1]))
                    upstream.send(payload)
                    reply = upstream.recv(65535)
                    local.sendto(reply, self.client_address)
            except OSError:
                pass
            finally:
                capacity.release()

    servers = []
    try:
        for port in ports:
            servers.append(TCP((bind, port), Stream))
        if 17502 in ports:
            servers.append(UDP((bind, 17502), Datagram))
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        return servers, stopped
    except BaseException:
        for server in servers:
            server.server_close()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote-host", required=True)
    parser.add_argument("--stop-file")
    args = parser.parse_args()
    validate_remote(args.remote_host)
    servers, stopped = start_relays(args.remote_host)
    print("[READY] Private FUT21 relay, TCP and QoS UDP; club remains on host", flush=True)
    try:
        while not (args.stop_file and Path(args.stop_file).exists()):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
