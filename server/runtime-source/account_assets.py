"""Parallel, CRC-checked public card art. Account/game responses are never cached."""
from concurrent.futures import ThreadPoolExecutor, CancelledError
import http.client
import hashlib
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import re
import socket
import threading
import zlib

TUNABLES='/fut/items/images/backgrounds/itembgs/futitemraritytunables.json'
# These are the backgrounds FIFA requests serially during current FUT startup.
WARM_RARITIES={19,38,63,85,98}
HOP={'connection','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','transfer-encoding','upgrade'}


class CardArt:
    def __init__(self, opener, stopped, cache=None):
        self.opener,self.stopped=opener,stopped
        self.lock=threading.Lock()
        self.pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='card-art')
        self.entries={}
        self.cache=Path(cache) if cache is not None else Path(os.environ.get('LOCALAPPDATA',Path.home()))/'MNG21/card-art-cache'
        self.local=threading.local()
        self.channels=set()

    def close(self):
        self.pool.shutdown(wait=False,cancel_futures=True)
        with self.lock:
            for channel in self.channels:channel.close()
            self.channels.clear()

    def configure(self, body):
        specs=[]
        for rarity in json.loads(body).get('rarities',[]):
            rid=rarity.get('id');guid=rarity.get('guid','')
            if rid not in WARM_RARITIES or not re.fullmatch('[a-fA-F0-9-]{36}',guid):
                continue
            for letter,field in [('s','smallItemCRC'),('c','collapsedItemCRC'),('e','largeItemCRC'),('j','jumboItemCRC')]:
                values=rarity.get(field,[])
                if len(values)!=1 or type(values[0]) is not int:
                    continue
                path=f'/fut/items/images/backgrounds/itemBGs/{guid}/cards_bg_{letter}_1_{rid}_0.dds'
                specs.append((path,values[0]&0xffffffff))
        with self.lock:
            previous=self.entries
            self.entries={}
            for path,crc in specs[:48]:
                old=previous.get(path.lower())
                future=old[1] if old and old[0]==crc else self.pool.submit(self.fetch,path,crc)
                self.entries[path.lower()]=(crc,future)

    def fetch(self,path,crc):
        if self.stopped.is_set():
            raise OSError('Connector stopped')
        target=self.cache/(hashlib.sha256(path.lower().encode()).hexdigest()+f'-{crc:08x}.dds')
        def valid(body):return len(body)<=1024*1024 and body[:4]==b'DDS ' and zlib.crc32(body)&0xffffffff==crc
        try:
            if target.is_file():
                body=target.read_bytes()
                if valid(body):return 200,[('Content-Type','application/octet-stream')],body
        except OSError:pass
        channel=getattr(self.local,'channel',None)
        if channel is None:
            channel=http.client.HTTPConnection('localhost');channel.sock=self.opener(8090)
            channel.connect=lambda: (_ for _ in ()).throw(OSError('Channel closed'))
            with self.lock:
                if self.stopped.is_set():channel.close();raise OSError('Connector stopped')
                self.channels.add(channel)
            self.local.channel=channel
        try:
            channel.request('GET',path)
            response=channel.getresponse()
            body=response.read(1024*1024+1)
            if response.status!=200 or not valid(body):
                raise OSError('Card image checksum mismatch')
            try:
                target.parent.mkdir(parents=True,exist_ok=True)
                temporary=target.with_suffix(f'.{threading.get_ident()}.tmp')
                temporary.write_bytes(body);temporary.replace(target)
            except OSError:pass
            return response.status,response.getheaders(),body
        except (OSError,http.client.HTTPException):
            self.local.channel=None
            with self.lock:self.channels.discard(channel)
            channel.close()
            raise OSError('Card image unavailable')

    def get(self,path):
        with self.lock:entry=self.entries.get(path.lower())
        if entry:
            try:return entry[1].result(timeout=12)
            except (OSError,ValueError,TimeoutError,CancelledError):pass
        return None


def handler(opener,stopped,capacity,art):
    class HTTP(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'

        def setup(self):
            super().setup()
            self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            self.upstream=None

        def finish(self):
            if self.upstream:self.upstream.close()
            super().finish()

        def handle(self):
            if not capacity.acquire(False):return
            try:super().handle()
            finally:capacity.release()

        def log_message(self,*args):pass

        def forward(self):
            # Keep all account/mutation requests live, in their original order.
            # Never retry a request after sending any of it upstream.
            if self.headers.get('Transfer-Encoding'):
                self.send_error(501,'Unsupported request framing');return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=16*1024*1024:raise ValueError('Request too large')
                body=self.rfile.read(length)
                if len(body)!=length:raise OSError('Incomplete request')
                result=art.get(self.path) if self.command=='GET' and not body else None
                if result is None:
                    if self.upstream is None:
                        self.upstream=http.client.HTTPConnection('localhost')
                        self.upstream.sock=opener(8090)
                        # Reconnection must always use the pinned/authenticated channel.
                        self.upstream.connect=lambda: (_ for _ in ()).throw(OSError('Channel closed'))
                    headers={k:v for k,v in self.headers.items() if k.lower() not in HOP}
                    self.upstream.request(self.command,self.path,body=body,headers=headers)
                    response=self.upstream.getresponse()
                    result=response.status,response.getheaders(),response.read()
                    if response.will_close:
                        self.upstream.close();self.upstream=None
                status,headers,payload=result
                if status==200 and self.command=='GET' and self.path.lower()==TUNABLES:
                    try:art.configure(payload)
                    except (ValueError,TypeError,RuntimeError):pass
                self.send_response_only(status)
                for key,value in headers:
                    if key.lower() not in HOP and key.lower()!='content-length':self.send_header(key,value)
                response_length=next((v for k,v in headers if k.lower()=='content-length'),str(len(payload))) if self.command=='HEAD' else str(len(payload))
                self.send_header('Content-Length',response_length)
                self.end_headers()
                if self.command!='HEAD':self.wfile.write(payload)
            except (OSError,ValueError,http.client.HTTPException):
                self.close_connection=True
                self.send_error(502,'Club connection interrupted')

        do_GET=do_POST=do_PUT=do_DELETE=do_OPTIONS=do_HEAD=forward
    return HTTP
