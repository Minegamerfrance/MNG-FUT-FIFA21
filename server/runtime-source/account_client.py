"""Local game channels authenticated with the existing MNG launcher account."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import socketserver
import struct
import threading
import time

from account_transport import PORTS, connect, receive_exact, relay
from account_assets import CardArt, handler as asset_handler


def credentials(path):
    session = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    token = session.get('token')
    account = session.get('profile', {}).get('id')
    if not isinstance(token, str) or not 16 <= len(token) <= 4096 or type(account) is not int or account <= 0:
        raise ValueError('Connecte-toi a ton compte dans MNG FUT.')
    return token, account


class TCP(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False


class UDP(socketserver.ThreadingUDPServer):
    daemon_threads = True
    allow_reuse_address = False


def start(config, token, account, ports=PORTS, bind='127.0.0.1'):
    if not ipaddress.ip_address(bind).is_loopback:
        raise ValueError('Le connecteur doit rester local au PC joueur')
    stopped = threading.Event()
    capacity = threading.BoundedSemaphore(64)

    def open_stream(port):
        # Retry only before forwarding any game bytes. Never replay a purchase
        # or squad save after an established connection has been interrupted.
        deadline = time.monotonic() + 12
        while True:
            try:
                return connect(config, token, port, account)[0]
            except OSError:
                if stopped.is_set() or time.monotonic() >= deadline:
                    raise
                stopped.wait(0.5)

    class Stream(socketserver.BaseRequestHandler):
        def handle(self):
            if not capacity.acquire(False):
                return
            try:
                with open_stream(self.server.server_address[1]) as remote:
                    relay(self.request, remote, stopped)
            except (OSError, ValueError):
                print('[CHANNEL] Connexion au club indisponible', flush=True)
            finally:
                capacity.release()

    class Datagram(socketserver.BaseRequestHandler):
        def handle(self):
            if not capacity.acquire(False):
                return
            try:
                data, local = self.request
                if len(data) > 65507:
                    return
                with connect(config, token, 'qos-udp', account)[0] as remote:
                    remote.sendall(struct.pack('!I', len(data)) + data)
                    size = struct.unpack('!I', receive_exact(remote, 4))[0]
                    if size > 65507:
                        raise ValueError('Invalid UDP reply')
                    local.sendto(receive_exact(remote, size), self.client_address)
            except (OSError, ValueError):
                pass
            finally:
                capacity.release()

    art=CardArt(open_stream,stopped)
    http_handler=asset_handler(open_stream,stopped,capacity,art)
    servers = []
    try:
        for port in ports:
            servers.append(TCP((bind, port), http_handler if port==8090 else Stream))
        if 17502 in ports:
            servers.append(UDP((bind, 17502), Datagram))
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        def close_art():
            stopped.wait()
            art.close()
        threading.Thread(target=close_art,daemon=True).start()
        return servers, stopped
    except BaseException:
        art.close()
        for server in servers:
            server.server_close()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--remote-host', required=True)
    parser.add_argument('--account-config', required=True)
    parser.add_argument('--session-file', required=True)
    parser.add_argument('--account-id', type=int, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads(Path(args.account_config).read_text(encoding='utf-8-sig'))
    if config.get('host') != args.remote_host or not re.fullmatch('[a-fA-F0-9]{64}', config.get('certificateSha256', '')):
        raise ValueError('Configuration serveur MNG invalide')
    token, account = credentials(args.session_file)
    if account != args.account_id:
        raise ValueError('Le compte a change. Relance la connexion dans MNG FUT.')
    with connect(config, token, 'ping', account)[0]:
        pass
    print('[AUTH] Compte MNG verifie; sauvegarde personnelle sur le VPS', flush=True)
    if args.check:
        return
    servers, stopped = start(config, token, account)
    print('[READY] Club personnel connecte; Tailscale non requis', flush=True)
    try:
        while credentials(args.session_file) == (token, account):
            time.sleep(1)
    except (KeyboardInterrupt, OSError, ValueError, KeyError):
        pass
    finally:
        stopped.set()
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print('Connexion MNG impossible:', error, flush=True)
        raise SystemExit(1)
