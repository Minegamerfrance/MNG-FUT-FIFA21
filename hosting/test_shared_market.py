"""Real temporary club DBs: escrow, bids, settlement, concurrency and rollback."""
from concurrent.futures import ThreadPoolExecutor
import ast,json,os,sqlite3,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]/'server/runtime-source/localfut21'
sys.path.insert(0,str(ROOT))
from shared_market import Market,MarketError,TRADE_BASE,dispatch,service,dto
source=ast.parse((ROOT/'server.py').read_text(encoding='utf-8-sig'))
definition=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='State')
methods=[n for n in definition.body if isinstance(n,ast.FunctionDef) and n.name in ('add_credits','spend_credits','next_item_id')]
namespace={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Accounting',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])),str(ROOT/'server.py'),'exec'),namespace)

class SharedMarket(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.now=int(time.time());self.market=Market(self.root)
  for identity in (1,2,3):
   path=self.root/'clubs'/str(identity)/'runtime/data/localfut15.sqlite3';path.parent.mkdir(parents=True)
   db=sqlite3.connect(path)
   db.executescript('CREATE TABLE kv(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE items(id INTEGER PRIMARY KEY,resource_id INTEGER,pile TEXT,data TEXT);CREATE TABLE squads(id INTEGER PRIMARY KEY,data TEXT);')
   db.executemany('INSERT INTO kv VALUES(?,?)',[('credits','10000'),('next_item_id','900000000000')]);db.commit();db.close()
  self.item=dict(id=101,resourceId=1001,assetId=1001,pile='trade',itemType='player',rating=81,rareflag=1,
                 name='Test Player',preferredPosition='CM',teamid=21,leagueId=19,nation=21,contract=38,untradeable=False)
  self.insert(1,self.item)
 def tearDown(self):self.tmp.cleanup()
 def db(self,identity):return sqlite3.connect(self.market.club_path(identity),timeout=30)
 def insert(self,identity,item):
  db=self.db(identity)
  with db:db.execute('INSERT INTO items VALUES(?,?,?,?)',(item['id'],item['resourceId'],item['pile'],json.dumps(item)))
  db.close()
 def balance(self,identity):
  db=self.db(identity)
  try:return int(json.loads(db.execute("SELECT value FROM kv WHERE key='credits'").fetchone()[0]))
  finally:db.close()
 def items(self,identity):
  db=self.db(identity)
  try:return [json.loads(row[0]) for row in db.execute('SELECT data FROM items')]
  finally:db.close()
 def listing(self,buy=1000):return self.market.list_item(1,101,500,buy,3600,'Player1',self.now)
 def assert_error(self,reason,call):
  with self.assertRaises(MarketError) as raised:call()
  self.assertEqual(raised.exception.reason,reason)
 def test_buy_now_transfers_exact_card_and_tax_once(self):
  row=self.listing();self.assertEqual(self.items(1),[])
  self.assertEqual(self.listing()['id'],row['id'])
  sold=self.market.bid(2,row['id'],1000,self.now)
  self.assertEqual(sold['state'],'sold');self.assertEqual(self.balance(1),10950);self.assertEqual(self.balance(2),9000)
  item=self.items(2)[0];self.assertEqual(item['resourceId'],1001);self.assertNotEqual(item['id'],101)
  self.assertEqual(item['contract'],38);self.assertEqual(item['pile'],'unassigned');self.assertFalse(item['untradeable'])
  self.market.bid(2,row['id'],1000,self.now)
  self.assertEqual(len(self.items(2)),1);self.assertEqual(self.balance(1),10950)
  self.assert_error('AUCTION_EXPIRED',lambda:self.market.bid(3,row['id'],1000,self.now))
 def test_competing_buyers_cannot_duplicate_card_or_charge_twice(self):
  row=self.listing();barrier=threading.Barrier(2)
  def buy(identity):
   barrier.wait()
   try:self.market.bid(identity,row['id'],1000,self.now);return identity
   except MarketError:return None
  with ThreadPoolExecutor(2) as pool:winners=list(pool.map(buy,(2,3)))
  self.assertEqual(sum(x is not None for x in winners),1)
  self.assertEqual(len(self.items(2))+len(self.items(3)),1)
  self.assertEqual(sum(self.balance(i) for i in (1,2,3)),29950)
 def test_bid_reservation_refund_extension_and_offline_settlement(self):
  row=self.listing(buy=0)
  self.market.bid(2,row['id'],500,self.now);self.assertEqual(self.balance(2),9500)
  self.market.bid(3,row['id'],600,self.now+3590)
  self.assertEqual(self.balance(2),10000);self.assertEqual(self.balance(3),9400)
  self.assertEqual(self.market.get(row['id'])['expires'],self.now+3620)
  self.market.bid(3,row['id'],700,self.now+3591);self.market.bid(3,row['id'],700,self.now+3591)
  self.assertEqual(self.balance(3),9300)
  self.market.settle_due(self.now+3630);self.market.settle_due(self.now+3630)
  self.assertEqual(self.balance(1),10665);self.assertEqual(len(self.items(3)),1);self.assertEqual(len(self.items(2)),0)
  self.assertEqual(Market(self.root).get(row['id'])['winner'],3)
 def test_buy_now_refunds_prior_bidder_and_uses_own_reservation(self):
  row=self.listing();self.market.bid(2,row['id'],500,self.now)
  self.market.bid(3,row['id'],1000,self.now)
  self.assertEqual(self.balance(2),10000);self.assertEqual(self.balance(3),9000)
  s=SimpleNamespace(_native_pack_item=lambda x:x,now_s=lambda:self.now)
  self.assertEqual(dto(s,dict(self.market.get(row['id'])),2,True)['bidState'],'outbid')
  second=dict(self.item,id=102);self.insert(1,second)
  row=self.market.list_item(1,102,500,1000,3600,'Player1',self.now)
  self.market.bid(2,row['id'],500,self.now);self.market.bid(2,row['id'],1000,self.now)
  self.assertEqual(self.balance(2),9000)
 def test_expired_unsold_returns_card_and_can_be_relisted(self):
  row=self.listing();self.market.settle_due(self.now+3601)
  self.assertEqual(self.items(1)[0]['id'],101);self.assertEqual(self.items(1)[0]['itemState'],'free')
  newer=self.market.list_item(1,101,500,1000,3600,'Player1',self.now+3602)
  self.assertNotEqual(row['id'],newer['id']);self.assertEqual(self.items(1),[])
  self.assertEqual(self.market.get(row['id'])['seller_removed'],1)
 def test_ownership_untradeable_loans_and_squad_protection(self):
  self.assert_error('ITEM_NOT_OWNED',lambda:self.market.list_item(2,101,500,1000,3600,'P2',self.now))
  for flag,value in [('untradeable',True),('loans',1),('concept',True),('objectiveReward',True)]:
   item=dict(self.item,id=200,**{flag:value});self.insert(1,item)
   self.assert_error('ITEM_NOT_TRADEABLE_IN_TRANSFER_LIST',lambda:self.market.list_item(1,200,500,1000,3600,'P1',self.now))
   db=self.db(1);db.execute('DELETE FROM items WHERE id=200');db.commit();db.close()
  db=self.db(1);db.execute('INSERT INTO squads VALUES(1,?)',(json.dumps(dict(players=[dict(itemId=101)])),));db.commit();db.close()
  self.assert_error('ITEM_IN_SQUAD',lambda:self.listing())
 def test_insufficient_funds_self_purchase_and_rollback(self):
  row=self.listing();self.assert_error('CANNOT_BUY_OWN_ITEM',lambda:self.market.bid(1,row['id'],1000,self.now))
  db=self.db(2);db.execute("UPDATE kv SET value='50' WHERE key='credits'");db.commit();db.close()
  self.assert_error('NOT_ENOUGH_CREDITS',lambda:self.market.bid(2,row['id'],1000,self.now))
  self.assertEqual(self.balance(1),10000);self.assertEqual(self.balance(2),50)
  db=self.db(3);db.execute("CREATE TRIGGER fail_grant BEFORE INSERT ON items BEGIN SELECT RAISE(ABORT,'test'); END");db.commit();db.close()
  with self.assertRaises(sqlite3.IntegrityError):self.market.bid(3,row['id'],1000,self.now)
  self.assertEqual(self.balance(1),10000);self.assertEqual(self.balance(3),10000)
  self.assertEqual(self.market.get(row['id'])['state'],'active');self.assertEqual(self.items(3),[])
 def test_watchlists_are_private_and_sales_can_only_be_cleared_by_seller(self):
  row=self.listing();self.market.watch(2,[row['id']])
  self.assertEqual(len(self.market.watch(2)),1);self.assertEqual(self.market.watch(3),[])
  self.assert_error('AUCTION_STILL_ACTIVE',lambda:self.market.remove(1,row['id']))
  self.market.bid(2,row['id'],1000,self.now)
  self.assert_error('NOT_YOUR_AUCTION',lambda:self.market.remove(3,row['id']))
  self.market.remove(1,row['id']);self.assertEqual(self.market.get(row['id'])['seller_removed'],1)
  self.market.watch(2,[row['id']],remove=True);self.assertEqual(self.market.watch(2),[])
 def test_real_player_search_and_identity_cannot_fall_back_to_catalogue(self):
  class State:
   def __init__(self,outer):self.path=outer.market.club_path(2);self.outer=outer
   def credits(self):return self.outer.balance(2)
   def get(self,key,default=None):return True if key=='shared_market_legacy_migrated_v1' else default
  state=State(self)
  s=SimpleNamespace(STATE=state,CFG={'club_id':2},now_s=lambda:self.now,_native_pack_item=lambda x:x)
  old=os.environ.get('LOCALFUT_SHARED_MARKET_ROOT');os.environ['LOCALFUT_SHARED_MARKET_ROOT']=str(self.root)
  try:
   code,body=dispatch(s,'GET','/ut/game/fifa21/transfermarket',{},{});self.assertEqual(code,200);self.assertEqual(body['auctionInfo'],[])
   row=self.listing()
   code,body=dispatch(s,'GET','/ut/game/fifa21/transfermarket',{'leag':['19'],'maskedDefId':['1001']},{})
   self.assertEqual(body['auctionInfo'][0]['tradeId'],row['id'])
   s.CFG['club_id']=1
   self.assert_error('INVALID_MARKET_IDENTITY',lambda:service(s))
  finally:
   if old is None:os.environ.pop('LOCALFUT_SHARED_MARKET_ROOT',None)
   else:os.environ['LOCALFUT_SHARED_MARKET_ROOT']=old
 def accounting(self,identity):
  state=namespace['Accounting']();state.conn=sqlite3.connect(self.market.club_path(identity),timeout=30,check_same_thread=False)
  state.lock=threading.RLock();return state
 def test_native_income_does_not_overwrite_a_concurrent_sale(self):
  row=self.listing();state=self.accounting(1)
  try:
   with ThreadPoolExecutor(2) as pool:
    income=pool.submit(lambda:[state.add_credits(1) for _ in range(100)])
    sale=pool.submit(self.market.bid,2,row['id'],1000,self.now)
    income.result();sale.result()
   self.assertEqual(self.balance(1),11050)
  finally:state.conn.close()
 def test_retail_delete_alias_removes_sold_tile_without_repaying_or_deleting_buyer_card(self):
  row=self.listing();self.market.bid(2,row['id'],1000,self.now)
  class State:
   def __init__(self,outer,identity):self.outer=outer;self.identity=identity;self.path=outer.market.club_path(identity)
   def get(self,key,default=None):return True if key=='shared_market_legacy_migrated_v1' else default
   def credits(self):return self.outer.balance(self.identity)
  s=SimpleNamespace(STATE=State(self,1),CFG={'club_id':1},now_s=lambda:self.now,_native_pack_item=lambda x:x)
  old=os.environ.get('LOCALFUT_SHARED_MARKET_ROOT');os.environ['LOCALFUT_SHARED_MARKET_ROOT']=str(self.root)
  try:
   path=f"/ut/delete/game/fifa21/trade/{row['id']}"
   balances=[self.balance(i) for i in (1,2)];buyer_items=self.items(2)
   for _ in range(2):self.assertEqual(dispatch(s,'GET',path,{},None)[0],200)
   self.assertEqual(self.market.get(row['id'])['seller_removed'],1)
   self.assertEqual([self.balance(i) for i in (1,2)],balances);self.assertEqual(self.items(2),buyer_items)
   result=dispatch(s,'GET','/ut/game/fifa21/trade/status',{'tradeIds':[str(row['id'])]},None)
   self.assertEqual(result[1]['auctionInfo'],[])
   s.STATE=State(self,3);s.CFG['club_id']=3
   self.assertEqual(dispatch(s,'GET',path,{},None)[0],403)
   self.insert(1,dict(self.item,id=102))
   active=self.market.list_item(1,102,500,1000,3600,'P1',self.now)
   s.STATE=State(self,1);s.CFG['club_id']=1
   self.assertEqual(dispatch(s,'GET',f"/ut/delete/game/fifa21/trade/{active['id']}",{},None)[0],403)
  finally:
   if old is None:os.environ.pop('LOCALFUT_SHARED_MARKET_ROOT',None)
   else:os.environ['LOCALFUT_SHARED_MARKET_ROOT']=old
 def test_native_debits_and_item_allocators_are_atomic(self):
  first=self.accounting(2);second=self.accounting(2)
  try:
   with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda s:s.spend_credits(8000),(first,second)))
   self.assertEqual(sorted(results),[False,True]);self.assertEqual(self.balance(2),2000)
   with ThreadPoolExecutor(2) as pool:
    a=pool.submit(lambda:[first.next_item_id() for _ in range(10)])
    b=pool.submit(lambda:[second.next_item_id() for _ in range(10)])
    self.assertEqual(len(set(a.result()+b.result())),20)
  finally:first.conn.close();second.conn.close()
 def test_interrupted_multi_club_transaction_recovers_without_partial_changes(self):
  code="import sys,os;sys.path.insert(0,sys.argv[1]);from shared_market import Market,change_coins;m=Market(sys.argv[2]);c=m.connection((1,2),True);db=c.__enter__();change_coins(db,'a1',-1000);change_coins(db,'a2',1000);db.execute(\"INSERT INTO events(kind) VALUES('interrupted')\");os._exit(17)"
  result=subprocess.run([sys.executable,'-c',code,str(ROOT),str(self.root)],capture_output=True)
  self.assertEqual(result.returncode,17,result.stderr)
  self.assertEqual(self.balance(1),10000);self.assertEqual(self.balance(2),10000)
  with self.market.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)

if __name__=='__main__':unittest.main()
