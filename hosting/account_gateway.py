"""TLS account gateway. Each verified MNG account gets a separate FUT process/DB."""
import argparse
from collections import defaultdict, deque
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import sqlite3
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.request

from account_transport import PORTS, receive_exact, receive_message, relay, send_message

AUTH_API = 'https://mng-fut-api.minegamerfrance.workers.dev/api/me'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class Authenticator:
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()
        # Bound coordination memory while coalescing parallel channel opens
        # for the same token. Authentication still expires after 30 seconds.
        self.verification_locks = [threading.Lock() for _ in range(64)]
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def verify(self, token):
        if not isinstance(token, str) or not 16 <= len(token) <= 4096:
            raise ValueError('Invalid session')
        key = hashlib.sha256(token.encode()).digest()
        with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
        with self.verification_locks[key[0] % len(self.verification_locks)]:
            with self.lock:
                cached = self.cache.get(key)
                if cached and cached[0] > time.monotonic():
                    return cached[1]
            return self._fetch(token, key)

    def _fetch(self, token, key):
        request = urllib.request.Request(AUTH_API, headers={'Authorization': 'Bearer ' + token,
            'Accept': 'application/json', 'User-Agent': 'MNG-FUT-Launcher/1.3.27'})
        with self.opener.open(request, timeout=8) as response:
            raw = response.read(16385)
        if len(raw) > 16384:
            raise ValueError('Invalid identity response')
        result = json.loads(raw)
        profile = result.get('profile', {})
        if result.get('ok') is not True or type(profile.get('id')) is not int or not 0 < profile['id'] < 100000000:
            raise ValueError('Invalid identity')
        profile = {'id': profile['id'], 'username': str(profile.get('username', 'MNGPlayer'))[:32]}
        with self.lock:
            if len(self.cache) >= 1024:
                self.cache = {k: v for k, v in self.cache.items() if v[0] > time.monotonic()}
                if len(self.cache) >= 1024:
                    self.cache.clear()
            self.cache[key] = time.monotonic() + 30, profile
        return profile


def certificate(root):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    cert, private = root / 'gateway.pem', root / 'gateway-key.pem'
    if cert.exists() != private.exists():
        raise ValueError('Incomplete gateway certificate; refusing to replace it')
    if not cert.exists():
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'MNG FUT21 Accounts')])
        now = datetime.now(timezone.utc)
        value = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                 .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
                 .not_valid_after(now + timedelta(days=365)).sign(key, hashes.SHA256()))
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        private.chmod(0o600)
        cert.write_bytes(value.public_bytes(serialization.Encoding.PEM))
    fingerprint = x509.load_pem_x509_certificate(cert.read_bytes()).fingerprint(hashes.SHA256()).hex()
    return cert, private, fingerprint


class Club:
    def __init__(self, root, profile, slot, server_script):
        self.root = root / 'clubs' / str(profile['id'])
        self.root.mkdir(parents=True, exist_ok=True)
        self.profile = profile
        self.address = '127.77.0.' + str(slot)
        self.server_script = server_script
        self.lock = threading.Lock()
        self.process = self.log = None
        self.channels = 0
        self.last_used = time.monotonic()

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return
            config = self.root / 'config'
            config.mkdir(exist_ok=True)
            path = config / 'config.json'
            if not path.exists():
                path.write_text(json.dumps(dict(display_name=self.profile['username'], club_name=self.profile['username'] + ' FC',
                    club_abbr='MNG', nucleus_id=1000000000 + self.profile['id'], persona_id=1100000000 + self.profile['id'],
                    club_id=self.profile['id'], starter_credits=10000, starter_fifa_points=1000)), encoding='utf-8')
            env = dict(os.environ, LOCALFUT21_USER_CONFIG_ROOT=str(config), LOCALFUT_RUNTIME_ROOT=str(self.root / 'runtime'),
                       LOCALAPPDATA=str(self.root / 'cache'))
            if self.log:
                self.log.close()
            self.log = (self.root / 'worker.log').open('ab')
            self.process = subprocess.Popen([sys.executable, '-u', str(self.server_script), '--host', self.address, '--lsx-mode', 'off'],
                                            env=env, stdout=self.log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('Club worker did not start')
                try:
                    for port in (8090, 44321, 10853, 17502):
                        with socket.create_connection((self.address, port), timeout=0.2):
                            pass
                    return
                except OSError:
                    time.sleep(0.2)
            self.stop()
            raise RuntimeError('Club startup timed out')

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log:
            self.log.close()
        self.process = self.log = None


class Clubs:
    def __init__(self, root, server_script, maximum=4):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.server_script = Path(server_script)
        self.maximum = maximum
        self.lock = threading.Lock()
        self.live = {}
        self.db = self.root / 'accounts.sqlite3'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, name TEXT NOT NULL, slot INTEGER UNIQUE NOT NULL)')

    def acquire(self, profile):
        with self.lock:
            identity = profile['id']
            if identity not in self.live:
                if len(self.live) >= self.maximum:
                    idle = [club for club in self.live.values() if club.channels == 0]
                    if not idle:
                        raise RuntimeError('Server capacity reached')
                    oldest = min(idle, key=lambda club: club.last_used)
                    oldest.stop()
                    del self.live[oldest.profile['id']]
                with closing(sqlite3.connect(self.db)) as db, db:
                    row = db.execute('SELECT slot FROM accounts WHERE id=?', (identity,)).fetchone()
                    if row:
                        slot = row[0]
                    else:
                        slot = db.execute('SELECT COALESCE(MAX(slot),0)+1 FROM accounts').fetchone()[0]
                        if slot > 240:
                            raise RuntimeError('Account capacity reached')
                        db.execute('INSERT INTO accounts VALUES(?,?,?)', (identity, profile['username'], slot))
                self.live[identity] = Club(self.root, profile, slot, self.server_script)
            club = self.live[identity]
            if club.channels >= 48:
                raise RuntimeError('Too many account channels')
            club.channels += 1
            return club

    def release(self, club):
        with self.lock:
            club.channels -= 1
            club.last_used = time.monotonic()


class Gateway(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, root, server_script, authenticator=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.clubs = Clubs(self.root, server_script)
        self.auth = authenticator or Authenticator()
        self.stopped = threading.Event()
        self.capacity = threading.BoundedSemaphore(96)
        self.failures = defaultdict(deque)
        self.failure_lock = threading.Lock()
        cert, key, self.fingerprint = certificate(self.root)
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(cert, key)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.capacity.acquire(False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.capacity.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.capacity.release()


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        gateway = self.server
        club = secure = None
        with gateway.failure_lock:
            if len(gateway.failures) >= 4096:
                gateway.failures.clear()
            failures = gateway.failures[self.client_address[0]]
            while failures and failures[0] < time.monotonic() - 60:
                failures.popleft()
            if len(failures) >= 10:
                return
        try:
            self.request.settimeout(10)
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            secure = gateway.context.wrap_socket(self.request, server_side=True)
            request = receive_message(secure)
            service = request.get('service')
            if request.get('version') != 1 or not (type(service) is int and service in PORTS or service in ('ping', 'qos-udp')):
                raise ValueError('Invalid service')
            profile = gateway.auth.verify(request.get('token'))
            if type(request.get('accountId')) is not int or request['accountId'] != profile['id']:
                raise ValueError('Identity mismatch')
            club = gateway.clubs.acquire(profile)
            club.start()
            send_message(secure, dict(ok=True, accountId=profile['id']))
            if service == 'ping':
                return
            if service == 'qos-udp':
                size = struct.unpack('!I', receive_exact(secure, 4))[0]
                if not 1 <= size <= 65507:
                    raise ValueError('Invalid datagram size')
                payload = receive_exact(secure, size)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.settimeout(3)
                    udp.connect((club.address, 17502))
                    udp.send(payload)
                    reply = udp.recv(65507)
                secure.sendall(struct.pack('!I', len(reply)) + reply)
            else:
                with socket.create_connection((club.address, service), timeout=5) as target:
                    relay(secure, target, gateway.stopped, lambda: gateway.auth.verify(request['token'])['id'] == profile['id'])
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            with gateway.failure_lock:
                failures.append(time.monotonic())
            if secure:
                try:
                    send_message(secure, dict(ok=False, error='Connexion refusee ou club indisponible. Reconnectez-vous dans MNG FUT.'))
                except OSError:
                    pass
        finally:
            if club:
                gateway.clubs.release(club)
            if secure:
                secure.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=51443)
    parser.add_argument('--data', default='/state/accounts')
    parser.add_argument('--server', default='/app/localfut21/server.py')
    args = parser.parse_args()
    with Gateway((args.host, args.port), args.data, args.server) as gateway:
        print(json.dumps(dict(ready=True, certificateSha256=gateway.fingerprint)), flush=True)
        def stop(*_):
            gateway.stopped.set()
            threading.Thread(target=gateway.shutdown, daemon=True).start()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            gateway.serve_forever(poll_interval=0.5)
        finally:
            gateway.stopped.set()
            for club in list(gateway.clubs.live.values()):
                with club.lock:
                    club.stop()


if __name__ == '__main__':
    main()
