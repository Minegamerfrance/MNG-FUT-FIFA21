import io,json,sys,threading,time,unittest,hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server/runtime-source'))
from account_gateway import Authenticator

class Opener:
    def __init__(self):self.calls=0;self.lock=threading.Lock()
    def open(self,request,timeout):
        with self.lock:self.calls+=1
        time.sleep(0.04)
        token=request.get_header('Authorization').split(' ',1)[1]
        identity=1 if token=='test-first-account-token' else 2
        return io.BytesIO(json.dumps({'ok':True,'profile':{'id':identity,'username':str(identity)}}).encode())

class AuthConcurrency(unittest.TestCase):
    def test_parallel_channels_share_one_verification(self):
        auth=Authenticator();auth.opener=Opener();barrier=threading.Barrier(8)
        def check(_):barrier.wait();return auth.verify('test-first-account-token')['id']
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(check,range(8))),[1]*8)
        self.assertEqual(auth.opener.calls,1)
        self.assertEqual(auth.verify('test-second-account-token')['id'],2)
        self.assertEqual(auth.opener.calls,2)
        key=hashlib.sha256(b'test-first-account-token').digest()
        auth.cache[key]=(0,{'id':1,'username':'1'})
        self.assertEqual(auth.verify('test-first-account-token')['id'],1)
        self.assertEqual(auth.opener.calls,3)
    def test_failed_identity_never_cached(self):
        auth=Authenticator()
        class Bad:
            def open(self,*args,**kwargs):return io.BytesIO(b'{"ok":false}')
        auth.opener=Bad()
        with self.assertRaises(ValueError):auth.verify('test-first-account-token')
        self.assertFalse(auth.cache)

if __name__=='__main__':unittest.main()
