"""Real HTTP connections; isolated origin, no account or club data."""
import http.client,json,socket,sys,tempfile,threading,time,unittest,zlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server/runtime-source'))
from account_assets import CardArt,handler,TUNABLES

GUID='a603331e-d10e-5f7b-a455-d4abac1d59ce'
PATH=f'/fut/items/images/backgrounds/itemBGs/{GUID}/cards_bg_s_1_19_0.dds'

class TestAssets(unittest.TestCase):
    def setUp(self):
        test=self
        self.image=b'DDS '+b'card-image'*100
        self.calls=[];self.active=self.maximum=0;self.lock=threading.Lock()
        class Origin(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def respond(self):
                body=self.rfile.read(int(self.headers.get('Content-Length',0)))
                with test.lock:test.calls.append((self.command,self.path,body))
                if self.path=='/ut/interrupted':
                    self.close_connection=True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                if self.path.lower()==TUNABLES:
                    crc=zlib.crc32(test.image)&0xffffffff
                    payload=json.dumps(dict(rarities=[dict(id=19,guid=GUID,**{field:[crc] for field in ('smallItemCRC','collapsedItemCRC','largeItemCRC','jumboItemCRC')})])).encode()
                elif self.path.endswith('.dds'):
                    with test.lock:
                        test.active+=1;test.maximum=max(test.maximum,test.active)
                    time.sleep(.06)
                    with test.lock:test.active-=1
                    payload=test.image
                else:payload=body or b'live-account'
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
                if self.command!='HEAD':self.wfile.write(payload)
            do_GET=do_POST=do_HEAD=respond
        self.origin=ThreadingHTTPServer(('127.0.0.1',0),Origin)
        def opener(port):
            self.assertEqual(port,8090)
            return socket.create_connection(self.origin.server_address,timeout=3)
        self.temp=tempfile.TemporaryDirectory(prefix='mng-art-test-')
        self.stopped=threading.Event();self.art=CardArt(opener,self.stopped,cache=self.temp.name)
        self.proxy=ThreadingHTTPServer(('127.0.0.1',0),handler(opener,self.stopped,threading.BoundedSemaphore(8),self.art))
        for server in (self.origin,self.proxy):threading.Thread(target=server.serve_forever,daemon=True).start()
        self.client=http.client.HTTPConnection(*self.proxy.server_address,timeout=5)

    def tearDown(self):
        self.client.close();self.stopped.set();self.art.close()
        for server in (self.proxy,self.origin):server.shutdown();server.server_close()
        self.temp.cleanup()

    def request(self,method,path,body=None):
        self.client.request(method,path,body=body);r=self.client.getresponse();data=r.read()
        self.assertEqual(r.status,200)
        return r,data

    def test_parallel_art_and_uncached_account_mutations(self):
        self.request('GET',TUNABLES)
        self.assertEqual(self.request('GET',PATH)[1],self.image)
        before=sum(path==PATH for _,path,_ in self.calls)
        self.assertEqual(self.request('GET',PATH)[1],self.image)
        self.assertEqual(sum(path==PATH for _,path,_ in self.calls),before)
        self.assertGreater(self.maximum,1)
        self.assertLessEqual(self.maximum,4)
        for _ in range(2):self.assertEqual(self.request('POST','/ut/save',b'one-mutation')[1],b'one-mutation')
        self.assertEqual(sum(path=='/ut/save' for _,path,_ in self.calls),2)
        response,data=self.request('HEAD','/ut/account')
        self.assertEqual(data,b'');self.assertEqual(int(response.getheader('Content-Length')),12)

    def test_changed_crc_invalidates_and_bad_crc_falls_back(self):
        self.request('GET',TUNABLES)
        self.assertEqual(self.request('GET',PATH)[1],self.image)
        self.image=b'DDS changed art'
        self.request('GET',TUNABLES)
        self.assertEqual(self.request('GET',PATH)[1],self.image)
        self.art.configure(json.dumps(dict(rarities=[dict(id=19,guid=GUID,smallItemCRC=[0])])).encode())
        self.assertEqual(self.request('GET',PATH)[1],self.image)

    def test_interrupted_mutation_is_never_replayed(self):
        self.client.request('POST','/ut/interrupted',body=b'purchase-once')
        response=self.client.getresponse();response.read()
        self.assertEqual(response.status,502)
        self.assertEqual(sum(path=='/ut/interrupted' for _,path,_ in self.calls),1)

    def test_verified_disk_cache_survives_connector_restart(self):
        _,tunables=self.request('GET',TUNABLES)
        for _,future in self.art.entries.values():future.result(timeout=3)
        before=len(self.calls)
        def no_network(port):raise AssertionError('Valid public art downloaded again')
        warm=CardArt(no_network,self.stopped,cache=self.temp.name)
        try:
            warm.configure(tunables)
            self.assertEqual(warm.get(PATH)[2],self.image)
            for _,future in warm.entries.values():future.result(timeout=3)
            self.assertEqual(len(self.calls),before)
        finally:warm.close()

if __name__=='__main__':unittest.main()
