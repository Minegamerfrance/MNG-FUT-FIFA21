from pathlib import Path
import os,sys,tempfile,json
r=Path(__file__).resolve().parent;p=r.parent/'runtime-source/localfut21'
w=Path(tempfile.mkdtemp(prefix='mng-season-rewards-'));os.environ['LOCALFUT_RUNTIME_ROOT']=str(w);os.environ['LOCALFUT21_USER_CONFIG_ROOT']=str(w/'config');sys.path.insert(0,str(p))
import server as s
s.STATE.set('scmp_user_xp',30000);s.STATE.set('scmp_claimed_levels',[])
for lvl in (2,3,5,6,10,13,15,16,20,23,25,26,27,28,30):
 res=s.season_persistence.claim_level(s,lvl)
 assert res['awards'][0]['untradeable']
 for i in res['grantedItems']:assert i['untradeable'] and i['untradeableCount']==1 and i['discardValue']==0
 assert s.season_persistence.claim_level(s,lvl)['alreadyClaimed']
token=next(i for i in s.STATE.list_items('unassigned') if i.get('seasonLevel')==3)
choices=s.STATE.redeem_player_pick(token['id']);selected=s.STATE.select_player_pick(token['id'],0)
card=s.STATE.get_item(choices[0]['id']);assert card['untradeable'] and card['seasonLevel']==3
# Route opens the identical shop template from a pending season reward.
s.STATE.clear_pile('unassigned')
status,h,b=s.route_fut('POST','/ut/game/fifa21/purchased/items',{'Content-Type':'application/json'},json.dumps({'packId':300}).encode())
assert status==200,(status,b)
items=[i for i in s.STATE.list_items('unassigned') if i.get('seasonLevel')==2];assert len(items)==12 and all(i['untradeable'] and i['seasonLevel']==2 for i in items)
assert not s.get_pack_cfg(300).get('untradeable'), 'Reward must not mutate shop configuration'
# Shop and explicitly vendable SBC still create tradable cards.
for reward in (None,{'source':'sbc','untradeable':False}):
 pack=s.STATE.create_pack(300,reward=reward)
 assert all(not i['untradeable'] for i in pack['itemData'])
# OVR across event types, then regulars; no rarity order ahead of rating.
rows=[dict(id=1,rating=99,rareflag=1),dict(id=2,rating=85,rareflag=21),dict(id=3,rating=86,rareflag=22),dict(id=4,rating=83,rareflag=37),dict(id=5,rating=80,rareflag=0)]
assert [i['id'] for i in sorted(rows,key=s._pack_reveal_sort_key)]==[3,2,4,1,5]
for packid in (300,303,404):
 pack=s.STATE.create_pack(packid,{'source':'season_level','levelId':22,'untradeable':True})
 data=pack['itemData'];assert data==sorted(data,key=s._pack_reveal_sort_key)
 assert [i['id'] for i in data]==sorted((i['id'] for i in data),reverse=True)
 assert [i['timestamp'] for i in data]==sorted((i['timestamp'] for i in data),reverse=True)
 assert all(i['untradeable'] for i in data)
ids=[i['id'] for i in data];s.STATE.conn.close();s.STATE=s.State(s.DB_PATH)
assert all(s.STATE.get_item(i)['untradeable'] for i in ids)
print('PASS: direct awards, choices, owned pack HTTP opening, unchanged shop/SBC, sorting special OVR then regular OVR, persisted order and restart')

