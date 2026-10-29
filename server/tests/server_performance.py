"""Search output parity and opt-in packet diagnostics, using an isolated club."""
import os,sys,tempfile,time,statistics
from pathlib import Path
from types import SimpleNamespace

p=Path(__file__).resolve().parents[1]/'runtime-source/localfut21'
w=Path(tempfile.mkdtemp(prefix='mng-perf-'))
os.environ['LOCALFUT_RUNTIME_ROOT']=str(w)
os.environ['LOCALFUT21_USER_CONFIG_ROOT']=str(w/'config')
sys.path.insert(0,str(p))
import server as s
inventory=s.fut_inventory
searches=[{'maskeddefid':182521},{'maskeddefid':'20801,182521'},
 {'defid':'0,67291385,100845817,0'},{'maskeddefid':182521,'pos':'CAM'},
 {'maskeddefid':182521,'rarity':19},{'assetid':20801,'maxrating':90},
 {'resourceid':182521},{'maskeddefid':999999999}]
def summary(rows):return [(r['id'],r['resourceId'],r['rating'],r['rareflag'],r['attributeList']) for r in rows]
for concept in [True,False]:
 full=inventory.catalogue(s,{},concept)
 for search in searches:
  expected=inventory.filter_items(full,search)
  actual=inventory.filter_items(inventory.catalogue(s,search,concept),search)
  assert summary(actual)==summary(expected),(concept,search)
times={}
for mode in ['full','selected']:
 samples=[]
 for _ in range(5):
  t=time.perf_counter()
  inventory.filter_items(inventory.catalogue(s,{} if mode=='full' else searches[0],True),searches[0])
  samples.append((time.perf_counter()-t)*1000)
 times[mode]=round(statistics.median(samples),2)
packet=SimpleNamespace(component=10,command=5,msg_num=123,raw=b'packet')
s.CFG['debug_packet_trace']=False
assert s._save_fire2(packet,('127.0.0.1',1)) is None
assert not list(s.LOGS.glob('fire2-*'))
s.CFG['debug_packet_trace']=True
saved=s._save_fire2(packet,('127.0.0.1',1))
assert saved.read_bytes()==b'packet' and saved.with_suffix('.hex.txt').is_file()
print('PASS: selected-player search matches full catalogue across 16 cases; diagnostics off by default and available on demand')
print('Median search milliseconds:',times)

# Empty and populated watchlists preserve results and do not construct
# unrelated player cards. Synthetic auction generations still expire.
original=inventory.catalogue
try:
 inventory.catalogue=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Empty watchlist built a catalogue'))
 assert inventory.dispatch(s,'GET','/ut/game/fifa21/watchlist',{},{} )[1]['auctionInfo']==[]
finally:inventory.catalogue=original
selected=original(s,{'type':'all','resourceid':182521})[0]
listing=inventory.auction(s,selected)
s.STATE.set('market_watchlist',[listing['tradeId']])
result=inventory.dispatch(s,'GET','/ut/game/fifa21/watchlist',{},{} )[1]
assert [x['tradeId'] for x in result['auctionInfo']]==[listing['tradeId']]
s.STATE.set('market_generation_182521',1)
assert not inventory.dispatch(s,'GET','/ut/game/fifa21/watchlist',{},{} )[1]['auctionInfo']
print('PASS: empty watchlist skips market; watched listing resolves; expired generation remains excluded')
