"""Isolated progression, reward, rollback and native API checks for Kroos."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'server/runtime-source/localfut21'
sys.path.insert(0, str(ROOT))
from kroos_objectives import Kroos, ROWS, SBC, LEVERKUSEN, BAYERN, FINAL, PACK


class Store:
    def __init__(self, path, cards):
        self.path, self.cards = path, cards
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path)
        self.conn.executescript('CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT);'
            'CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY,resource_id INTEGER,pile TEXT,data TEXT);'
            'CREATE TABLE IF NOT EXISTS unopened_packs(id INTEGER PRIMARY KEY,pack_id INTEGER,data TEXT);')

    def get(self, key, default=None):
        row = self.conn.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.conn:
            self.conn.execute('INSERT INTO kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                              (key, json.dumps(value)))

    def build_player_item(self, rid, iid, pile):
        return dict(self.cards[rid], id=iid, resourceId=rid, pile=pile)


class Career(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        custom = json.loads((ROOT/'custom-players.json').read_text(encoding='utf-8-sig'))
        self.cards = {rid: custom[str(rid)] for rid in (LEVERKUSEN, BAYERN, FINAL)}
        self.cards[182521] = dict(assetId=182521, leagueId=53, nation=21, teamid=243)
        self.store = Store(Path(self.tmp.name)/'test.sqlite3', self.cards)
        self.s = SimpleNamespace(STATE=self.store, PLAYER_DB=self.cards,
            _pack_award=lambda pid: dict(type='pack', assetId=pid),
            _scmp_award=lambda kind, rid: dict(type=kind, assetId=rid),
            _native_pack_item=lambda item: item, now_s=lambda: 123,
            PENDING_USERSESSION_REFRESH=threading.Event())
        self.c = Kroos()
        self.store.set('mng_active_match_mode', 'squad_battles')
        for iid, rid in ((100, LEVERKUSEN), (101, BAYERN), (102, 182521)):
            self.store.conn.execute('INSERT INTO items VALUES(?,?,?,?)', (iid, rid, 'club', '{}'))
        self.store.conn.commit()

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def unlock(self):
        self.store.set('sbc_completed', sorted(SBC))

    def save(self, counts=None, claimed=None):
        p = self.c.progress(self.s)
        if counts is not None:
            p['counts'] = counts
        if claimed is not None:
            p['claimedObjectives'] = claimed
        self.store.set(self.c.key, p)

    def start(self, rid=LEVERKUSEN, iid=100, index=0, **flags):
        item = dict(id=iid, resourceId=rid, **flags)
        self.c.start(self.s, {}, dict(squad=dict(players=[dict(index=index, itemData=item)])))

    def finish(self, iid=100, result='WIN', **stats):
        self.c.finish(self.s, dict(endReason=result, items=[dict(id=iid, **stats)]))

    def counts(self):
        return self.c.progress(self.s)['counts']

    def test_existing_sbc_and_reward_once(self):
        self.store.set('sbc_completed', sorted(SBC)[:3])
        self.assertEqual(self.counts()[0], 0)
        self.assertEqual(self.c.claim(self.s, 0)[0], 403)
        self.unlock()
        self.assertEqual(self.counts()[0], 1)
        self.assertEqual(self.c.claim(self.s, 0)[0], 200)
        self.assertTrue(self.c.claim(self.s, 0)[1]['alreadyClaimed'])
        self.assertEqual(self.store.conn.execute('SELECT pack_id FROM unopened_packs').fetchall(), [(PACK,)])

    def test_correct_version_and_snapshot_only(self):
        self.start()
        self.unlock()  # Finishing an SBC during this match does not rewrite its snapshot.
        self.finish(goals=3, assists=2)
        self.assertEqual(self.counts()[1:], [0]*8)
        self.start(); self.finish(goals=3, assists=2)
        self.assertEqual(self.counts()[1:5], [1, 3, 2, 1])
        self.finish(goals=3, assists=2)  # Repeated result cannot count twice.
        self.assertEqual(self.counts()[1:5], [1, 3, 2, 1])
        self.start(182521, 102); self.finish(iid=102, goals=10, assists=10)
        self.assertEqual(self.counts()[1:5], [1, 3, 2, 1])
        self.start(BAYERN, 101); self.finish(iid=101, goals=5)
        self.assertEqual(self.counts()[5:], [0]*4)

    def test_bench_concepts_unowned_abandoned_and_duplicate_start(self):
        self.unlock()
        for flags, iid in ((dict(concept=True),100), (dict(dream=True),100), ({},999)):
            self.start(iid=iid, **flags); self.finish(iid=iid, goals=5)
        self.assertEqual(self.counts()[1:], [0]*8)
        self.start(index=11); self.finish(goals=0, assists=0)
        self.assertEqual(self.counts()[1:5], [0]*4)
        self.start(index=11); self.finish(goals=1, assists=2)
        self.assertEqual(self.counts()[1:5], [1, 1, 2, 0])
        self.start(); self.finish(result='QUIT', goals=8)
        self.assertEqual(self.counts()[1:5], [1, 1, 2, 0])
        self.start(); self.start(BAYERN,101); self.finish(goals=1)
        self.assertEqual(self.counts()[1:5], [2, 2, 2, 1])

    def test_event_stats_and_other_players(self):
        self.unlock(); self.start()
        self.c.finish(self.s, dict(endReason='LOSS', events=[
            dict(attributes=[dict(key='name',value='goal'), dict(key='player_id',value=182521)]),
            dict(attributes=[dict(key='name',value='assist'), dict(key='player_id',value=str(LEVERKUSEN))]),
            dict(attributes=[dict(key='name',value='goal'), dict(key='player_id',value=999)]),
        ]))
        self.assertEqual(self.counts()[1:5], [1,1,1,0])

    def test_bayern_unlock_and_group_rewards_survive_reopen(self):
        self.unlock()
        counts=[row[1] for row in ROWS]; counts[5:]=[0]*4
        self.save(counts)
        self.assertEqual(self.c.claim(self.s)[0],403)
        self.c.claim(self.s,4)
        reward=self.store.conn.execute('SELECT resource_id,data FROM items WHERE pile=?',('unassigned',)).fetchone()
        self.assertEqual(reward[0],BAYERN)
        self.assertTrue(json.loads(reward[1])['untradeable'])
        self.start(BAYERN,101); self.finish(iid=101,goals=2,assists=3)
        self.assertEqual(self.counts()[5:],[1,2,3,1])
        self.save([row[1] for row in ROWS])
        for i in range(len(ROWS)):
            self.assertEqual(self.c.claim(self.s,i)[0],200)
            self.assertTrue(self.c.claim(self.s,i)[1]['alreadyClaimed'])
        self.c.claim(self.s)
        self.assertTrue(self.c.claim(self.s)[1]['alreadyClaimed'])
        self.assertEqual(self.store.conn.execute('SELECT COUNT(*) FROM unopened_packs WHERE pack_id=?',(PACK,)).fetchone()[0],8)
        self.assertEqual(self.store.conn.execute('SELECT resource_id FROM items WHERE pile=? ORDER BY id',('unassigned',)).fetchall(),[(BAYERN,),(FINAL,)])
        self.store.conn.close();self.store.conn=sqlite3.connect(self.store.path)
        self.assertTrue(self.c.claim(self.s)[1]['alreadyClaimed'])
        self.assertEqual(self.counts(),[row[1] for row in ROWS])

    def test_reward_failure_rolls_back_receipt(self):
        self.unlock()
        self.store.conn.execute("CREATE TRIGGER block_pack BEFORE INSERT ON unopened_packs BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.claim(self.s,0)
        self.assertNotIn(0,self.c.progress(self.s)['claimedObjectives'])
        self.store.conn.execute('DROP TRIGGER block_pack')
        self.assertFalse(self.c.claim(self.s,0)[1]['alreadyClaimed'])


class NativeApi(unittest.TestCase):
    def test_native_category_card_previews_and_pack_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ['LOCALFUT_RUNTIME_ROOT']=tmp
            os.environ['LOCALFUT21_USER_CONFIG_ROOT']=str(Path(tmp)/'config')
            os.environ['LOCALFUT_TEST_MODE']='1'
            import server
            try:
                campaign=server._scmp_campaign_json()
                category=next(c for c in campaign['scmpCategoryProgressList'] if c['name']=='MNG FUT')
                group=category['groupsList'][0]
                self.assertEqual(group['objectivesCount'],9)
                self.assertEqual(group['awardsList'][0]['type'],'item')
                self.assertEqual(server.PLAYER_DB[LEVERKUSEN]['rating'],75)
                self.assertEqual(server.PLAYER_DB[BAYERN]['rating'],85)
                self.assertEqual(server.PLAYER_DB[BAYERN]['teamid'],21)
                self.assertEqual(server.PLAYER_DB[FINAL]['rating'],90)
                self.assertEqual(server.get_pack_cfg(PACK)['rare_slots'],2)
                for method in ('GET','PUT','POST'):
                    code,_,raw=server.route_fut(method,'/ut/game/fifa21/scmp/active/category/73/details',{},b'{}')
                    self.assertEqual(code,200)
                    self.assertEqual(json.loads(raw)['groupsList'][0]['groupId'],7301)
                career=server.league_objectives.CAMPAIGNS[7301]
                server.STATE.set('sbc_completed',sorted(SBC))
                p=career.progress(server);p['counts']=[row[1] for row in ROWS]
                server.STATE.set(career.key,p)
                baseline=server.STATE.conn.execute('SELECT COUNT(*) FROM unopened_packs WHERE pack_id=?',(PACK,)).fetchone()[0]
                for index in range(9):
                    path=f'/ut/game/fifa21/scmp/campaign/group/7301/objective/{730101+index}/rewards'
                    code,_,raw=server.route_fut('POST',path,{},b'{}')
                    self.assertEqual(code,200)
                self.assertEqual(server.STATE.conn.execute('SELECT COUNT(*) FROM unopened_packs WHERE pack_id=?',(PACK,)).fetchone()[0],baseline+8)
                path='/ut/game/fifa21/scmp/campaign/group/7301/rewards'
                code,_,raw=server.route_fut('POST',path,{},b'{}')
                self.assertEqual(code,200)
                self.assertFalse(json.loads(raw)['alreadyClaimed'])
                code,_,raw=server.route_fut('POST',path,{},b'{}')
                self.assertTrue(json.loads(raw)['alreadyClaimed'])
                granted=server.STATE.conn.execute('SELECT resource_id,data FROM items WHERE resource_id IN (?,?)',(BAYERN,FINAL)).fetchall()
                self.assertEqual(sorted(row[0] for row in granted),sorted([BAYERN,FINAL]))
                self.assertTrue(all(json.loads(row[1])['untradeable'] for row in granted))
            finally:
                server.STATE.conn.close()
                import logging
                for handler in logging.getLogger().handlers[:]:
                    logging.getLogger().removeHandler(handler);handler.close()


if __name__=='__main__':
    unittest.main()
