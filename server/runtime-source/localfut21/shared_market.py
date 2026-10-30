"""Persistent player-only market with SQLite super-journal settlements.

Cards are escrowed, bids reserve coins, and the market plus participating club
databases commit together in DELETE/FULL journal mode. No synthetic stock.
"""
from contextlib import contextmanager
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time

def price_limits(meta):
    if str(meta.get('itemType', 'player')) != 'player':
        return 150, 15000000
    rating = int(meta.get('rating', 0) or 0)
    rarity = int(meta.get('rareflag', 0) or 0)
    if rarity == 12:
        if rating >= 92: return 1500000, 15000000
        if rating >= 90: return 750000, 8000000
        if rating >= 88: return 350000, 2500000
        if rating >= 85: return 150000, 900000
    elif rarity > 1 or meta.get('special'):
        if rating >= 91: return 500000, 5000000
        if rating >= 88: return 200000, 1500000
        if rating >= 85: return 70000, 500000
        if rating >= 80: return 30000, 200000
    elif rating >= 75:
        if rarity == 0: return 350, 10000
        if rating >= 92: return 500000, 4000000
        if rating >= 90: return 250000, 2000000
        if rating >= 89: return 100000, 900000
        if rating >= 87: return 35000, 350000
        if rating >= 85: return 12000, 150000
        if rating >= 83: return 4000, 60000
        if rating >= 80: return 1500, 30000
        return 700, 15000
    return 150, 15000000


TRADE_BASE = 400000000000
ITEM_TOP = 8000000000000
DURATIONS = (3600,10800,21600,43200,86400,259200)


class MarketError(Exception):
    def __init__(self, reason, status=400):
        super().__init__(reason)
        self.reason,self.status=reason,status


class Retry(Exception): pass


def integer(value, default=0):
    try:return int(value)
    except (ValueError,TypeError):return default


def step(price):
    return 50 if price<1000 else 100 if price<10000 else 250 if price<50000 else 500 if price<100000 else 1000


def valid_price(price):
    return 150<=price<=15000000 and price % step(price)==0


@lru_cache(maxsize=1)
def icon_release_policy():
    return json.loads(Path(__file__).with_name('icon-release-policy.json').read_text(encoding='utf-8'))


def icon_available(meta):
    rarity=integer(meta.get('rareflag'))
    if rarity not in (12,84):return True
    policy=icon_release_policy()
    return not policy.get('baseOnly') or (rarity==12 and integer(meta.get('resourceId')) in policy['baseResourceIds'])


def put(db, alias, key, value):
    db.execute(f'INSERT INTO {alias}.kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
               (key,json.dumps(value)))


def credits(db, alias):
    row=db.execute(f"SELECT value FROM {alias}.kv WHERE key='credits'").fetchone()
    if row is None:raise MarketError('CLUB_BALANCE_UNAVAILABLE',503)
    return int(json.loads(row[0]))


def change_coins(db, alias, delta):
    row=db.execute(f"UPDATE {alias}.kv SET value=CAST(CAST(value AS INTEGER)+? AS TEXT) "
                   "WHERE key='credits' AND CAST(value AS INTEGER)+?>=0",(delta,delta))
    if row.rowcount!=1:raise MarketError('NOT_ENOUGH_CREDITS',458)
    put(db,alias,'shared_market_refresh',time.time_ns())


class Market:
    def __init__(self, root):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'transfermarket.sqlite3'
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auctions(
                  id INTEGER PRIMARY KEY,seller INTEGER NOT NULL,item_id INTEGER NOT NULL,
                  item TEXT NOT NULL,seller_name TEXT NOT NULL,start INTEGER NOT NULL,buy INTEGER NOT NULL,
                  created INTEGER NOT NULL,expires INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'active',
                  high_bidder INTEGER NOT NULL DEFAULT 0,current INTEGER NOT NULL DEFAULT 0,
                  offers INTEGER NOT NULL DEFAULT 0,winner INTEGER NOT NULL DEFAULT 0,
                  won_item TEXT NOT NULL DEFAULT '',sale_kind TEXT NOT NULL DEFAULT '',
                  seller_removed INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS market_due ON auctions(state,expires);
                CREATE INDEX IF NOT EXISTS market_seller ON auctions(seller,seller_removed);
                CREATE TABLE IF NOT EXISTS watch(account INTEGER,trade_id INTEGER,PRIMARY KEY(account,trade_id));
                CREATE TABLE IF NOT EXISTS bids(trade_id INTEGER,account INTEGER,amount INTEGER,at INTEGER,
                  PRIMARY KEY(trade_id,account));
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,trade_id INTEGER,kind TEXT,
                  actor INTEGER,at INTEGER,data TEXT);
            ''')

    def club_path(self, identity):
        identity=integer(identity)
        if identity<=0:raise MarketError('INVALID_ACCOUNT',403)
        path=self.root/'clubs'/str(identity)/'runtime/data/localfut15.sqlite3'
        if not path.is_file():raise MarketError('CLUB_NOT_FOUND',404)
        return path

    @contextmanager
    def connection(self, accounts=(), transaction=False):
        db=sqlite3.connect(self.path,timeout=30,isolation_level=None,uri=True)
        db.row_factory=sqlite3.Row
        try:
            if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0].lower()!='delete':
                raise MarketError('MARKET_JOURNAL_UNAVAILABLE',503)
            db.execute('PRAGMA synchronous=FULL')
            for identity in sorted(set(integer(x) for x in accounts if integer(x)>0)):
                alias='a'+str(identity)
                db.execute(f'ATTACH DATABASE ? AS {alias}',(self.club_path(identity).as_uri()+'?mode=rw',))
                if db.execute(f'PRAGMA {alias}.journal_mode=DELETE').fetchone()[0].lower()!='delete':
                    raise MarketError('CLUB_JOURNAL_UNAVAILABLE',503)
                db.execute(f'PRAGMA {alias}.synchronous=FULL')
            if transaction:db.execute('BEGIN IMMEDIATE')
            yield db
            if transaction:db.commit()
        except BaseException:
            if db.in_transaction:db.rollback()
            raise
        finally:db.close()

    def record(self, db, tid, kind, actor, now, **data):
        db.execute('INSERT INTO events(trade_id,kind,actor,at,data) VALUES(?,?,?,?,?)',
                   (tid,kind,actor,now,json.dumps(data)))

    def get(self, tid, db=None):
        if db is not None:return db.execute('SELECT * FROM auctions WHERE id=?',(tid,)).fetchone()
        with self.connection() as connection:return self.get(tid,connection)

    def transact(self, tid, actor, action):
        for _ in range(6):
            snapshot=self.get(tid)
            if snapshot is None:raise MarketError('UNKNOWN_AUCTION',404)
            people={integer(actor),snapshot['seller'],snapshot['high_bidder']}-{0}
            try:
                with self.connection(people,True) as db:
                    row=self.get(tid,db)
                    if row['high_bidder'] and row['high_bidder'] not in people:raise Retry()
                    return action(db,row)
            except Retry:continue
        raise MarketError('AUCTION_BUSY_RETRY',409)

    def grant(self, db, row, buyer, price, now):
        alias='a'+str(buyer)
        item=json.loads(row['item'])
        # Global descending market IDs never race the native ascending allocator.
        identifier=ITEM_TOP-row['id']
        if db.execute(f'SELECT 1 FROM {alias}.items WHERE id=?',(identifier,)).fetchone():
            raise MarketError('ITEM_ID_COLLISION',409)
        item.update(id=identifier,pile='unassigned',itemState='free',marketPurchase=True,
                    lastSalePrice=price,timestamp=now,owners=integer(item.get('owners'),1)+1)
        for key in ('tradeId','tradeState','expires','duplicate','isDuplicate'):item.pop(key,None)
        if item.get('itemType','player')=='player' and db.execute(
                f'SELECT 1 FROM {alias}.items WHERE resource_id=? LIMIT 1',(item['resourceId'],)).fetchone():
            item.update(duplicate=True,isDuplicate=True)
        db.execute(f'INSERT INTO {alias}.items(id,resource_id,pile,data) VALUES(?,?,?,?)',
                   (identifier,item['resourceId'],'unassigned',json.dumps(item)))
        next_row=db.execute(f"SELECT value FROM {alias}.kv WHERE key='next_item_id'").fetchone()
        put(db,alias,'next_item_id',max(identifier,integer(json.loads(next_row[0])) if next_row else 0))
        put(db,alias,'shared_market_refresh',time.time_ns())
        return item

    def sell(self, db, row, buyer, price, now, kind):
        fee=price*5//100
        change_coins(db,'a'+str(row['seller']),price-fee)
        item=self.grant(db,row,buyer,price,now)
        db.execute("UPDATE auctions SET state='sold',winner=?,high_bidder=?,current=?,won_item=?,sale_kind=?,offers=offers+? WHERE id=?",
                   (buyer,buyer,price,json.dumps(item),kind,int(kind=='buyNow'),row['id']))
        db.execute('INSERT OR IGNORE INTO watch VALUES(?,?)',(buyer,row['id']))
        self.record(db,row['id'],'sale',buyer,now,price=price,fee=fee,seller=row['seller'],itemId=item['id'])
        return self.get(row['id'],db)

    def expire(self, db, row, now):
        if row['state']!='active' or row['expires']>now:return row
        if row['high_bidder']:
            return self.sell(db,row,row['high_bidder'],row['current'],now,'auction')
        item=json.loads(row['item']);item.update(pile='trade',itemState='free')
        alias='a'+str(row['seller'])
        db.execute(f'INSERT INTO {alias}.items(id,resource_id,pile,data) VALUES(?,?,?,?)',
                   (row['item_id'],item['resourceId'],'trade',json.dumps(item)))
        put(db,alias,'shared_market_refresh',time.time_ns())
        db.execute("UPDATE auctions SET state='expired' WHERE id=?",(row['id'],))
        self.record(db,row['id'],'expired',row['seller'],now)
        return self.get(row['id'],db)

    def settle_due(self, now=None):
        now=int(time.time()) if now is None else now
        with self.connection() as db:
            due=[r[0] for r in db.execute("SELECT id FROM auctions WHERE state='active' AND expires<=? ORDER BY expires LIMIT 100",(now,))]
        settled=0
        for tid in due:
            try:
                self.transact(tid,0,lambda db,row:self.expire(db,row,now));settled+=1
            except (sqlite3.Error,MarketError):
                logging.getLogger(__name__).exception('Auction settlement deferred trade=%s',tid)
        return settled

    def list_item(self, seller, iid, start, buy, duration, name, now=None):
        now=int(time.time()) if now is None else now
        if duration not in DURATIONS:raise MarketError('INVALID_DURATION')
        if not valid_price(start) or buy and (not valid_price(buy) or buy<start):
            raise MarketError('INVALID_PRICE_RANGE')
        with self.connection((seller,),True) as db:
            existing=db.execute("SELECT * FROM auctions WHERE seller=? AND item_id=? AND state='active'",(seller,iid)).fetchone()
            if existing:return dict(existing)
            alias='a'+str(seller)
            stored=db.execute(f'SELECT data,pile FROM {alias}.items WHERE id=?',(iid,)).fetchone()
            if stored is None:raise MarketError('ITEM_NOT_OWNED',403)
            item=json.loads(stored['data'])
            if not icon_available(item):raise MarketError('ICON_VERSION_NOT_RELEASED',403)
            floor,ceiling=price_limits(item)
            if not floor<=start<=ceiling or buy and not floor<=buy<=ceiling:
                raise MarketError('INVALID_PRICE_RANGE')
            if stored['pile']!='trade' or item.get('untradeable') or integer(item.get('untradeableCount'))>0 or any(
                    item.get(k) for k in ('concept','dream','objectiveReward','ballonDorLoan')) or integer(item.get('loans'))>0:
                raise MarketError('ITEM_NOT_TRADEABLE_IN_TRANSFER_LIST',403)
            # Never list a card still referenced by an active or saved squad.
            for squad in db.execute(f'SELECT data FROM {alias}.squads'):
                document=json.loads(squad[0])
                for slot in document.get('players',[]):
                    data=slot.get('itemData') or {}
                    if iid in {integer(slot.get('itemId')),integer(slot.get('id')),integer(data.get('id'))}:
                        raise MarketError('ITEM_IN_SQUAD',403)
            if db.execute("SELECT COUNT(*) FROM auctions WHERE seller=? AND seller_removed=0 AND state IN ('active','sold')",(seller,)).fetchone()[0]>=100:
                raise MarketError('TRANSFER_LIST_FULL',403)
            tid=db.execute('SELECT COALESCE(MAX(id),?)+1 FROM auctions',(TRADE_BASE,)).fetchone()[0]
            db.execute("UPDATE auctions SET seller_removed=1 WHERE seller=? AND item_id=? AND state='expired'",(seller,iid))
            item.update(pile='trade',itemState='forSale')
            db.execute('INSERT INTO auctions(id,seller,item_id,item,seller_name,start,buy,created,expires) VALUES(?,?,?,?,?,?,?,?,?)',
                       (tid,seller,iid,json.dumps(item),name,start,buy,now,now+duration))
            db.execute(f'DELETE FROM {alias}.items WHERE id=?',(iid,))
            put(db,alias,'shared_market_refresh',time.time_ns())
            self.record(db,tid,'listed',seller,now,itemId=iid,start=start,buy=buy)
            return dict(self.get(tid,db))

    def bid(self, buyer, tid, amount, now=None):
        now=int(time.time()) if now is None else now
        self.settle_due(now)
        def action(db,row):
            row=self.expire(db,row,now)
            if row['state']=='sold' and row['winner']==buyer:return dict(row)
            if row['state']!='active':raise MarketError('AUCTION_EXPIRED',460)
            if not icon_available(json.loads(row['item'])):raise MarketError('ICON_VERSION_NOT_RELEASED',403)
            if row['seller']==buyer:raise MarketError('CANNOT_BUY_OWN_ITEM',403)
            if row['high_bidder']==buyer and row['current']==amount:return dict(row)
            alias='a'+str(buyer)
            watch_count=db.execute('SELECT COUNT(*) FROM watch WHERE account=?',(buyer,)).fetchone()[0]
            watched=db.execute('SELECT 1 FROM watch WHERE account=? AND trade_id=?',(buyer,tid)).fetchone()
            if watch_count>=50 and not watched:raise MarketError('WATCHLIST_FULL',403)
            if row['buy'] and amount>=row['buy']:
                price=row['buy']
                change_coins(db,alias,-(price-row['current'] if row['high_bidder']==buyer else price))
                if row['high_bidder'] and row['high_bidder']!=buyer:
                    change_coins(db,'a'+str(row['high_bidder']),row['current'])
                return dict(self.sell(db,row,buyer,price,now,'buyNow'))
            ceiling=max(price_limits(json.loads(row['item']))[1],row['start'],row['buy'],row['current'])
            if amount>ceiling:raise MarketError('BID_TOO_HIGH',400)
            minimum=row['current']+step(row['current']) if row['current'] else row['start']
            if not valid_price(amount) or amount<minimum:raise MarketError('BID_TOO_LOW',457)
            change_coins(db,alias,-(amount-row['current'] if row['high_bidder']==buyer else amount))
            if row['high_bidder'] and row['high_bidder']!=buyer:
                change_coins(db,'a'+str(row['high_bidder']),row['current'])
            db.execute('UPDATE auctions SET high_bidder=?,current=?,offers=offers+1,expires=MAX(expires,?) WHERE id=?',
                       (buyer,amount,now+30,tid))
            db.execute('INSERT INTO bids VALUES(?,?,?,?) ON CONFLICT(trade_id,account) DO UPDATE SET amount=excluded.amount,at=excluded.at',
                       (tid,buyer,amount,now))
            db.execute('INSERT OR IGNORE INTO watch VALUES(?,?)',(buyer,tid))
            self.record(db,tid,'bid',buyer,now,amount=amount)
            return dict(self.get(tid,db))
        return self.transact(tid,buyer,action)

    def rows(self, where='1', parameters=()):
        with self.connection() as db:return [dict(row) for row in db.execute('SELECT * FROM auctions WHERE '+where,parameters)]

    def watch(self, actor, trade_ids=(), remove=False, clear=False):
        with self.connection(transaction=True) as db:
            if clear:db.execute('DELETE FROM watch WHERE account=?',(actor,))
            for tid in set(trade_ids):
                if remove:db.execute('DELETE FROM watch WHERE account=? AND trade_id=?',(actor,tid));continue
                if self.get(tid,db) is None:raise MarketError('UNKNOWN_AUCTION',404)
                if db.execute('SELECT COUNT(*) FROM watch WHERE account=?',(actor,)).fetchone()[0]>=50 and not db.execute(
                        'SELECT 1 FROM watch WHERE account=? AND trade_id=?',(actor,tid)).fetchone():raise MarketError('WATCHLIST_FULL',403)
                db.execute('INSERT OR IGNORE INTO watch VALUES(?,?)',(actor,tid))
            return [dict(r) for r in db.execute('SELECT a.* FROM auctions a JOIN watch w ON w.trade_id=a.id WHERE w.account=?',(actor,))]

    def remove(self, seller, tid):
        def action(db,row):
            if row['seller']!=seller:raise MarketError('NOT_YOUR_AUCTION',403)
            row=self.expire(db,row,int(time.time()))
            if row['state']=='active':raise MarketError('AUCTION_STILL_ACTIVE',403)
            db.execute('UPDATE auctions SET seller_removed=1 WHERE id=?',(tid,))
            return True
        return self.transact(tid,seller,action)


@lru_cache(maxsize=8)
def market(root):return Market(root)


def service(s):
    root=os.environ.get('LOCALFUT_SHARED_MARKET_ROOT','')
    if not root:return None
    result=market(root)
    identity=integer(s.CFG.get('club_id'))
    if identity<=0 or Path(s.STATE.path).resolve()!=result.club_path(identity).resolve():
        raise MarketError('INVALID_MARKET_IDENTITY',403)
    if not s.STATE.get('shared_market_legacy_migrated_v1'):
        with s.STATE.lock:
            if not s.STATE.get('shared_market_legacy_migrated_v1'):
                old=s.STATE.conn.execute("SELECT key,value FROM kv WHERE key LIKE 'owned_auction_%'").fetchall()
                for key,value in old:
                    if not re.fullmatch(r'owned_auction_\d+',key):continue
                    data=json.loads(value);iid=integer(data.get('itemId'))
                    item=s.STATE.get_item(iid)
                    if item is None:continue
                    migrated=False
                    if integer(data.get('expiresAt'))>s.now_s():
                        try:
                            result.list_item(identity,iid,integer(data.get('startingBid')),integer(data.get('buyNowPrice')),
                                integer(data.get('expiresAt'))-integer(data.get('created')),
                                str(s.CFG.get('display_name','MNG FUT')),integer(data.get('created')))
                            migrated=True
                        except MarketError:pass
                    if not migrated:
                        item['itemState']='free'
                        with s.STATE.conn:s.STATE.conn.execute('UPDATE items SET data=? WHERE id=?',(json.dumps(item),iid))
                with s.STATE.conn:
                    s.STATE.conn.execute("DELETE FROM kv WHERE key LIKE 'owned_auction_%'")
                    put(s.STATE.conn,'main','shared_market_legacy_migrated_v1',True)
    return result,identity


def dto(s,row,actor,watched=False):
    item=json.loads(row['won_item'] if row['winner']==actor and row['won_item'] else row['item'])
    if item.get('itemType')=='training' and row['state']=='active':item['id']=ITEM_TOP-row['id']
    if row['state']=='expired':item['itemState']='free'
    state='active' if row['state']=='active' else 'closed' if row['state']=='sold' else 'expired'
    bid='highest' if row['high_bidder']==actor else 'none'
    if row['state']=='sold' and row['winner']==actor:bid='buyNow' if row['sale_kind']=='buyNow' else 'highest'
    elif watched and row['high_bidder'] and row['high_bidder']!=actor:bid='outbid'
    return dict(tradeId=row['id'],itemData=s._native_pack_item(item),startingBid=row['start'],buyNowPrice=row['buy'],
        currentBid=row['current'],offers=row['offers'],expires=max(-1,row['expires']-s.now_s()) if state=='active' else -1,
        tradeState=state,bidState=bid,watched=watched,sellerName=row['seller_name'],sellerEstablished=0)


def tradepile(s, svc=None):
    configured=svc or service(s)
    if configured is None:return None
    store,actor=configured;store.settle_due(s.now_s())
    rows=store.rows('seller=? AND seller_removed=0',(actor,))
    owned=s.STATE.list_items('trade');by_id={integer(item['id']):item for item in owned}
    visible=[row for row in rows if row['state']!='expired' or row['item_id'] in by_id]
    represented={row['item_id'] for row in visible}
    auctions=[dto(s,row,actor) for row in visible]
    auctions.extend(dict(tradeId=0,itemData=s._native_pack_item(item),tradeState='inactive',bidState='none',
        startingBid=0,currentBid=0,buyNowPrice=0,offers=0,expires=-1,watched=False)
        for item in owned if integer(item['id']) not in represented)
    return dict(auctionInfo=auctions,credits=s.STATE.credits(),total=len(auctions),count=len(auctions),
        maxAuctionsAllowed=100,offered=0,selling=sum(a['tradeState']=='active' for a in auctions),
        sold=sum(a['tradeState']=='closed' for a in auctions),itemData=[])


def hub(s):
    configured=service(s)
    if configured is None:return None
    store,actor=configured;pile=tradepile(s,configured);watch=store.watch(actor)
    return dict(auctionCount=len(store.rows("state='active'")),
        tradePile=dict(count=pile['count'],selling=pile['selling'],sold=pile['sold']),
        watchlist=dict(count=len(watch),outbid=sum(r['high_bidder'] not in (0,actor) for r in watch),
                       winning=sum(r['high_bidder']==actor and r['state']=='active' for r in watch)))


_refresh_versions={}
def poll_refresh(s):
    if not os.environ.get('LOCALFUT_SHARED_MARKET_ROOT'):return
    version=s.STATE.get('shared_market_refresh')
    key=str(s.STATE.path)
    if version is not None and _refresh_versions.get(key)!=version:
        _refresh_versions[key]=version
        s.PENDING_USERSESSION_REFRESH.set()


def dispatch(s, method, path, query, payload):
    # Retail FIFA 21 tunnels this DELETE through a GET to /ut/delete/.
    # Limit the alias to the observed trade-removal route; ownership and
    # active-auction checks still run through Market.remove below.
    legacy_delete=re.fullmatch(r'/ut/delete/game/fifa21/trade/(\d+)',path)
    if legacy_delete and method in ('GET','POST','DELETE'):
        path='/ut/game/fifa21/trade/'+legacy_delete.group(1)
        method='DELETE'
    relevant=path in ('/ut/game/fifa21/transfermarket','/ut/game/fifa21/tradepile',
        '/ut/game/fifa21/watchlist','/ut/game/fifa21/watchlist/items',
        '/ut/game/fifa21/trade/status','/ut/game/fifa21/trade/status/lite') or re.match(
        r'^/ut/game/fifa21/(auctionhouse|trade/|tradepile/)',path)
    if not relevant or not os.environ.get('LOCALFUT_SHARED_MARKET_ROOT'):return None
    import fut_inventory as inventory
    try:
        store,actor=service(s)
        store.settle_due(s.now_s())
        search=inventory.criteria(query,payload)
        if path=='/ut/game/fifa21/transfermarket' and method in ('GET','POST'):
            all_rows=store.rows("state='active' AND seller<>?",(actor,))
            offers=[]
            for row in all_rows:
                item=json.loads(row['item'])
                if not icon_available(item):continue
                item.update(id=row['id'],buyNowPrice=row['buy'] or row['current'] or row['start'])
                offers.append(item)
            filtered=inventory.filter_items(offers,search)
            low=integer(inventory.value(search,'micr','minbuy','minprice'))
            high=integer(inventory.value(search,'macr','maxbuy','maxprice'),15000000)
            minbid=integer(inventory.value(search,'minb'));maxbid=integer(inventory.value(search,'maxb'),15000000)
            by_id={row['id']:row for row in all_rows}
            filtered=[item for item in filtered if (by_id[item['id']]['buy'] or not low and high==15000000) and low<=(by_id[item['id']]['buy'] or 15000000)<=high and
                      minbid<=max(by_id[item['id']]['current'],by_id[item['id']]['start'])<=maxbid]
            # Native transfer search pages must be chronological, independent
            # of inventory filtering's default overall-rating sort.
            filtered.sort(key=lambda item:(by_id[item['id']]['expires'],item['id']))
            selected=inventory.page(filtered,search)
            return 200,dict(auctionInfo=[dto(s,by_id[item['id']],actor) for item in selected],
                            credits=s.STATE.credits(),total=len(filtered),count=len(selected))
        if path=='/ut/game/fifa21/auctionhouse' and method=='POST':
            if not isinstance(payload,dict) or not isinstance(payload.get('itemData'),dict):raise MarketError('INVALID_LISTING')
            row=store.list_item(actor,integer(payload['itemData'].get('id')),integer(payload.get('startingBid')),
                integer(payload.get('buyNowPrice')),integer(payload.get('duration')),
                str(s.CFG.get('display_name','MNG FUT')),s.now_s())
            s.PENDING_USERSESSION_REFRESH.set()
            return 200,dict(id=row['id'],tradeId=row['id'],auctionInfo=[dto(s,row,actor)],credits=s.STATE.credits())
        bid=re.fullmatch(r'/ut/game/fifa21/trade/(\d+)/(bid|offer)',path)
        if bid and method in ('PUT','POST'):
            row=store.bid(actor,int(bid.group(1)),integer(inventory.value(search,'bid','buynowprice')),s.now_s())
            s.PENDING_USERSESSION_REFRESH.set()
            items=[json.loads(row['won_item'])] if row['state']=='sold' and row['winner']==actor else []
            return 200,dict(auctionInfo=[dto(s,row,actor,True)],credits=s.STATE.credits(),itemData=[s._native_pack_item(i) for i in items])
        if path=='/ut/game/fifa21/tradepile' and method=='GET':return 200,tradepile(s,(store,actor))
        single=re.fullmatch(r'/ut/game/fifa21/trade/(\d+)',path)
        if single and method=='DELETE':
            store.remove(actor,int(single.group(1)));return 200,dict(success=True,credits=s.STATE.credits())
        if path in ('/ut/game/fifa21/trade/status','/ut/game/fifa21/trade/status/lite') or single and method=='GET':
            wanted={int(single.group(1))} if single else inventory.ids(inventory.value(search,'tradeids','tradeid'))
            rows=[r for tid in wanted for r in [store.get(tid)] if r is not None
                  and not (r['seller']==actor and r['seller_removed'])]
            watched={r['id'] for r in store.watch(actor)}
            return 200,dict(auctionInfo=[dto(s,dict(row),actor,row['id'] in watched) for row in rows],credits=s.STATE.credits())
        if path in ('/ut/game/fifa21/watchlist','/ut/game/fifa21/watchlist/items'):
            ids=inventory.ids(inventory.value(search,'tradeid','tradeids','id'))
            rows=store.watch(actor,ids,remove=method=='DELETE',clear=method=='DELETE' and not ids)
            return 200,dict(auctionInfo=[dto(s,r,actor,True) for r in rows],credits=s.STATE.credits())
        if path in ('/ut/game/fifa21/auctionhouse/relist','/ut/game/fifa21/auctionhouse/relistall','/ut/game/fifa21/tradepile/relist') and method in ('POST','PUT'):
            rows=[]
            for old in store.rows("seller=? AND state='expired' AND seller_removed=0",(actor,)):
                if s.STATE.get_item(old['item_id']) is None:continue
                rows.append(store.list_item(actor,old['item_id'],old['start'],old['buy'],3600,
                    str(s.CFG.get('display_name','MNG FUT')),s.now_s()))
            return 200,dict(auctionInfo=[dto(s,row,actor) for row in rows],credits=s.STATE.credits())
        if path=='/ut/game/fifa21/tradepile/sold' and method=='DELETE':
            for row in store.rows("seller=? AND state='sold' AND seller_removed=0",(actor,)):store.remove(actor,row['id'])
            return 200,dict(success=True,credits=s.STATE.credits())
        return 404,dict(reason='UNKNOWN_MARKET_OPERATION')
    except MarketError as error:return error.status,dict(reason=error.reason,credits=s.STATE.credits())
    except sqlite3.OperationalError:
        s.log.exception('Shared market is temporarily unavailable')
        return 503,dict(reason='MARKET_BUSY_RETRY',credits=s.STATE.credits())
