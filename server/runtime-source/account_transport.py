"""Bounded, certificate-pinned transport for authenticated MNG club channels."""
import hashlib
import hmac
import json
import select
import socket
import ssl
import struct
import time

PORTS = (8090, 44321, 10853, 17502, 42232, 8081, 42231)


def send_message(connection, message):
    data = json.dumps(message, separators=(',', ':')).encode()
    if len(data) > 8192:
        raise ValueError('Message too large')
    connection.sendall(struct.pack('!I', len(data)) + data)


def receive_exact(connection, size):
    data = bytearray()
    while len(data) < size:
        block = connection.recv(size - len(data))
        if not block:
            raise ConnectionError('Channel closed')
        data.extend(block)
    return bytes(data)


def receive_message(connection):
    size = struct.unpack('!I', receive_exact(connection, 4))[0]
    if not 1 <= size <= 8192:
        raise ValueError('Invalid message size')
    result = json.loads(receive_exact(connection, size))
    if not isinstance(result, dict):
        raise ValueError('Invalid message')
    return result


def connect(config, token, service, account_id):
    # A self-signed certificate is accepted ONLY after checking its shipped pin.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    raw = socket.create_connection((config['host'], int(config['port'])), timeout=12)
    raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    secure = None
    try:
        secure = context.wrap_socket(raw, server_hostname=config['host'])
        pin = hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest()
        if not hmac.compare_digest(pin, config['certificateSha256'].lower()):
            raise ValueError('Certificat MNG non reconnu. Aucun identifiant envoye.')
        secure.settimeout(65)
        send_message(secure, dict(version=1, token=token, service=service, accountId=account_id))
        result = receive_message(secure)
        if not result.get('ok') or result.get('accountId') != account_id:
            raise ConnectionError(result.get('error', 'Compte MNG non reconnu'))
        return secure, result
    except BaseException:
        (secure or raw).close()
        raise


def relay(first, second, stopped, valid=lambda: True):
    # FUT exchanges many short request/reply packets. Do not hold them for
    # Nagle batching while waiting for the peer's delayed acknowledgement.
    for connection in (first, second):
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    first.settimeout(10)
    second.settimeout(10)
    activity = checked = time.monotonic()
    while not stopped.is_set():
        now = time.monotonic()
        if now - checked > 60:
            if not valid():
                return
            checked = now
        if now - activity > 900:
            return
        pending = [s for s in (first, second) if isinstance(s, ssl.SSLSocket) and s.pending()]
        for source in pending or select.select([first, second], [], [], 0.5)[0]:
            block = source.recv(65536)
            if not block:
                return
            (second if source is first else first).sendall(block)
            activity = time.monotonic()
