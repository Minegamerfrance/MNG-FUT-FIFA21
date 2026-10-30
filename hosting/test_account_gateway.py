import hashlib
import http.client
from contextlib import closing
import json
from pathlib import Path
import socket
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server/runtime-source'))
from account_transport import connect, receive_exact
from account_gateway import Gateway


class FakeAuth:
    def __init__(self):
        self.calls = 0

    def verify(self, token):
        self.calls += 1
        if token not in ('test-account-one-token', 'test-account-two-token'):
            raise ValueError('Invalid test identity')
        identity = 1 if token == 'test-account-one-token' else 2
        return dict(id=identity, username='Player' + str(identity))


class TestGateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='mng21-account-test-')
        cls.auth = FakeAuth()
        cls.gateway = Gateway(('127.0.0.1', 0), cls.temporary.name,
                              ROOT / 'server/runtime-source/localfut21/server.py', cls.auth)
        cls.thread = threading.Thread(target=cls.gateway.serve_forever, daemon=True)
        cls.thread.start()
        cls.config = dict(host='127.0.0.1', port=cls.gateway.server_address[1], certificateSha256=cls.gateway.fingerprint)

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stopped.set()
        cls.gateway.shutdown()
        cls.gateway.server_close()
        cls.thread.join()
        for club in cls.gateway.clubs.live.values():
            with club.lock:
                club.stop()
        cls.temporary.cleanup()

    def test_01_pin_before_credentials(self):
        before = self.auth.calls
        with self.assertRaisesRegex(ValueError, 'Certificat'):
            connect(dict(self.config, certificateSha256='0' * 64), 'test-account-one-token', 'ping', 1)
        self.assertEqual(self.auth.calls, before)

    def test_02_reject_invalid_and_impersonated_accounts(self):
        for token, account in [('invalid-token', 1), ('test-account-one-token', 2)]:
            with self.assertRaises(OSError):
                connect(self.config, token, 'ping', account)
        self.assertFalse(self.gateway.clubs.live)

    def test_03_two_clubs_persistence_and_channels(self):
        for account, token in [(1, 'test-account-one-token'), (2, 'test-account-two-token')]:
            with connect(self.config, token, 'ping', account)[0]:
                pass
            with connect(self.config, token, 8090, account)[0] as channel:
                channel.sendall(b'GET /localfut/auth/bootstrap HTTP/1.0\r\nHost: localhost\r\n\r\n')
                response = http.client.HTTPResponse(channel)
                response.begin()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())['version'], 1)
            with connect(self.config, token, 'qos-udp', account)[0] as channel:
                channel.sendall(struct.pack('!III', 8, 1234, 5678))
                size = struct.unpack('!I', receive_exact(channel, 4))[0]
                self.assertGreater(size, 0)
                self.assertEqual(len(receive_exact(channel, size)), size)
        first = self.gateway.clubs.live[1]
        second = self.gateway.clubs.live[2]
        self.assertNotEqual(first.address, second.address)
        self.assertNotEqual(first.root, second.root)
        for club in (first, second):
            with closing(sqlite3.connect(club.root / 'runtime/data/localfut15.sqlite3')) as db, db:
                self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
                db.execute('INSERT OR REPLACE INTO kv VALUES(?,?)', ('account_test_marker', json.dumps(club.profile['id'])))
        for club in (first, second):
            with club.lock:
                club.stop()
            club.start()
            with closing(sqlite3.connect(club.root / 'runtime/data/localfut15.sqlite3')) as db, db:
                self.assertEqual(json.loads(db.execute('SELECT value FROM kv WHERE key=?', ('account_test_marker',)).fetchone()[0]), club.profile['id'])


    def test_04_native_shared_market_between_two_authenticated_clubs(self):
        def request(account,method,path,payload=None):
            token='test-account-one-token' if account==1 else 'test-account-two-token'
            body=json.dumps(payload).encode() if payload is not None else b''
            with connect(self.config,token,8090,account)[0] as channel:
                header=f'{method} {path} HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n'.encode()
                channel.sendall(header+body)
                response=http.client.HTTPResponse(channel);response.begin()
                result=json.loads(response.read());self.assertEqual(response.status,200,result)
                return result
        for account,token in ((1,'test-account-one-token'),(2,'test-account-two-token')):
            with connect(self.config,token,'ping',account)[0]:pass
        self.assertEqual(request(2,'GET','/ut/game/fifa21/transfermarket')['auctionInfo'],[])
        seller=self.gateway.clubs.live[1]
        item=dict(id=900900000001,resourceId=182521,assetId=182521,itemType='player',pile='trade',
                  rating=85,rareflag=1,name='Kroos',preferredPosition='CM',teamid=243,leagueId=53,
                  nation=21,untradeable=False,contract=38)
        dbpath=seller.root/'runtime/data/localfut15.sqlite3'
        with closing(sqlite3.connect(dbpath)) as db,db:
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0],'delete')
            db.execute('INSERT INTO items VALUES(?,?,?,?)',(item['id'],item['resourceId'],'trade',json.dumps(item)))
        listing=request(1,'POST','/ut/game/fifa21/auctionhouse',dict(itemData={'id':item['id']},startingBid=500,buyNowPrice=1000,duration=3600))
        tid=listing['tradeId']
        found=request(2,'GET','/ut/game/fifa21/transfermarket?maskedDefId=182521')
        self.assertEqual(found['auctionInfo'][0]['tradeId'],tid)
        bought=request(2,'PUT',f'/ut/game/fifa21/trade/{tid}/bid',{'bid':1000})
        self.assertEqual(bought['credits'],9000)
        self.assertEqual(request(2,'PUT',f'/ut/game/fifa21/trade/{tid}/bid',{'bid':1000})['credits'],9000)
        sold=request(1,'GET','/ut/game/fifa21/tradepile')
        self.assertEqual(sold['credits'],10950);self.assertEqual(sold['sold'],1)
        self.assertEqual(request(2,'GET','/ut/game/fifa21/watchlist')['auctionInfo'][0]['tradeState'],'closed')
        won=request(2,'GET','/ut/game/fifa21/purchased/items')['itemData']
        self.assertEqual(sum(i.get('resourceId')==182521 for i in won),1)
        request(1,'DELETE',f'/ut/game/fifa21/trade/{tid}')
        self.assertEqual(request(1,'GET','/ut/game/fifa21/tradepile')['sold'],0)
        # The gateway, rather than a player's HTTP request, settles an expired bid.
        item['id']+=1
        with closing(sqlite3.connect(dbpath)) as db,db:
            db.execute('INSERT INTO items VALUES(?,?,?,?)',(item['id'],item['resourceId'],'trade',json.dumps(item)))
        tid=request(1,'POST','/ut/game/fifa21/auctionhouse',dict(itemData={'id':item['id']},startingBid=500,buyNowPrice=0,duration=3600))['tradeId']
        request(2,'PUT',f'/ut/game/fifa21/trade/{tid}/bid',{'bid':500})
        import time
        with closing(sqlite3.connect(Path(self.temporary.name)/'transfermarket.sqlite3')) as db,db:
            db.execute('UPDATE auctions SET expires=? WHERE id=?',(int(time.time())-1,tid))
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            with closing(sqlite3.connect(Path(self.temporary.name)/'transfermarket.sqlite3')) as db:
                if db.execute('SELECT state FROM auctions WHERE id=?',(tid,)).fetchone()[0]=='sold':break
            time.sleep(.1)
        else:self.fail('Gateway did not settle the offline auction.')
        self.assertEqual(request(1,'GET','/ut/game/fifa21/tradepile')['credits'],11425)


if __name__ == '__main__':
    unittest.main()
