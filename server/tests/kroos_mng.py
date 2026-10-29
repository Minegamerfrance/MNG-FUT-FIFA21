"""Isolated catalogue, native art and real four-exchange reward regression."""
import json,os,sys,tempfile,zlib
from pathlib import Path

p=Path(__file__).resolve().parents[1]/'runtime-source/localfut21'
w=Path(tempfile.mkdtemp(prefix='mng-kroos-'))
os.environ['LOCALFUT_RUNTIME_ROOT']=str(w)
os.environ['LOCALFUT21_USER_CONFIG_ROOT']=str(w/'config')
sys.path.insert(0,str(p))
import server as s

rid=67291385
m=s.PLAYER_DB[rid]
assert (m['assetId'],m['rating'],m['preferredPosition'],m['teamid'],m['rareflag'])==(182521,75,'CAM',32,19)
assert m['face']==[68,72,76,78,52,56] and not m['packEligible']
for edition,rating,position,club,face,wf in [
 (rid,75,'CAM',32,[68,72,76,78,52,56],3),
 (84068601,85,'CAM',21,[70,82,86,84,64,58],4),
 (100845817,90,'CM',243,[72,82,91,82,74,70],5)]:
 meta=s.PLAYER_DB[edition]
 assert (meta['rating'],meta['preferredPosition'],meta['teamid'],meta['face'],meta['skillMoves'],meta['weakFoot'])==(rating,position,club,face,3,wf)
 assert meta['rareflag']==19 and meta['catalogEnabled'] and not meta['packEligible']
 assert s._cached_dynamic_player_head(edition)==(p/f'custom-playerheads/p{edition}.dds').read_bytes()
 card=s.STATE.build_player_item(edition,123,'unassigned')
 for render in (s._native_pack_item,s._native_player_item):
  native=render(card)
  assert native['skillmoves']==2 and native['weakfootabilitytypecode']==wf
assert s.PLAYER_DB[182521]['rating']==88 and s.PLAYER_DB[182521]['teamid']==243
status,headers,body=s.route_fut('GET',f'/ut/game/fifa21/attributes/metadata?defIds=182521,{rid}',{},b'')
assert status==200 and all(x['attributeArray']==m['face'] for x in json.loads(body))
assert all(x['rating']==75 for x in json.loads(body))
spec=json.loads((p/'custom-backgrounds/rarity19.json').read_text(encoding='utf8'))
for letter,key in [('e','largeItemCRC'),('s','smallItemCRC'),('c','collapsedItemCRC'),('j','jumboItemCRC')]:
 data=s.league_objectives.background(s,f"/fut/items/images/backgrounds/itembgs/{spec['guid']}/cards_bg_{letter}_1_19_0.dds")
 assert zlib.crc32(data)&0xffffffff==spec[key][0]
assert s._cached_dynamic_player_head(rid)==(p/f'custom-playerheads/p{rid}.dds').read_bytes()
assert next(x for x in json.loads(s.league_objectives.tunables(s,b'{"rarities":[]}'))['rarities'] if x['id']==19)['name']=='MNG FUT'
category=next(c for c in s._sbc_sets_response()['categories'] if c['categoryId']==3)
assert category['sets'][0]['id']==910600
assert category['sets'][0]['priority']<category['sets'][1]['priority']
assert [s.cr7_flashback_sbc.RULES[x]['rating'] for x in range(910601,910605)]==[85,85,86,86]
assert [s.cr7_flashback_sbc.RULES[x].get('totw',0) for x in range(910601,910605)]==[0,1,0,1]
assert all(not s._SBC_CHAL_BY_INT[x]['rewards']['entries'] for x in range(910601,910605))

def lineup(totw=False):
 ids=[];assets=set()
 for r,meta in sorted(s.PLAYER_DB.items(),key=lambda x:0 if x[1].get('rareflag')==3 else 1):
  if meta['rating']<86 or meta.get('rareflag')!=(3 if totw and not ids else 1):continue
  asset=meta.get('assetId',r)
  if asset in assets:continue
  assets.add(asset)
  iid=s.STATE.next_item_id();item=s.STATE.build_player_item(r,iid,'club')
  s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',(iid,r,'club',json.dumps(item)))
  ids.append(iid)
  if len(ids)==11:break
 s.STATE.conn.commit()
 assert len(ids)==11
 return {'players':[dict(index=i,itemData=dict(id=iid)) for i,iid in enumerate(ids)]}

# Reject a missing TOTW without removing a single player.
payload=lineup();s.cr7_flashback_sbc.save(s,910602,payload)
status,result=s.cr7_flashback_sbc.submit(s,910602)
assert status==200 and result['success'] is False
assert all(s.STATE.get_item(x['itemData']['id']) for x in payload['players'])
for cid in range(910601,910605):
 payload=lineup(cid in (910602,910604))
 assert s.cr7_flashback_sbc.save(s,cid,payload)[0]==200
 status,result=s.cr7_flashback_sbc.submit(s,cid)
 assert status==200 and result['success'],result
 assert len(result['grantedItems'])==(1 if cid==910604 else 0)
 assert all(s.STATE.get_item(x['itemData']['id']) is None for x in payload['players'])
status,replay=s.cr7_flashback_sbc.submit(s,910604)
assert replay==result
rows=s.STATE.conn.execute('SELECT data FROM items WHERE resource_id=?',(rid,)).fetchall()
assert len(rows)==1
assert json.loads(rows[0][0])['untradeable']
assert all(str(s._SBC_CHAL_BY_INT[c]['id']) in s._sbc_completed() for c in range(910601,910605))
print('PASS: Kroos75 CAM Leverkusen, exact face stats, four valid DDS/CRC, custom head, rarity label, first MNG SBC, two TOTW requirements, four exchanges, single untradeable completion reward and idempotent retry')
