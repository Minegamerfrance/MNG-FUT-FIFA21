from pathlib import Path
import os,sys,tempfile,json,struct,zlib
p=Path(__file__).resolve().parents[1]/'runtime-source/localfut21'
w=Path(tempfile.mkdtemp(prefix='mng-prime-'));os.environ['LOCALFUT_RUNTIME_ROOT']=str(w);os.environ['LOCALFUT21_USER_CONFIG_ROOT']=str(w/'config');sys.path.insert(0,str(p))
import server as s
rid=67285499;m=s.PLAYER_DB[rid]
assert (m['assetId'],m['rating'],m['preferredPosition'],m['teamid'],m['rareflag'])==(176635,89,'CAM',1,38)
assert m['face']==[80,78,90,88,45,65] and not m['packEligible']
assert s.PLAYER_DB[176635]['rating']==82 and s.PLAYER_DB[176635]['rareflag']==1
card=s.STATE.build_player_item(rid,123,'unassigned')
for render in (s._native_pack_item,s._native_player_item):
 n=render(card);assert n['skillmoves']==3 and n['weakfootabilitytypecode']==2
spec=json.loads((p/'custom-backgrounds/rarity38.json').read_text())
for letter,key in [('e','largeItemCRC'),('s','smallItemCRC'),('c','collapsedItemCRC'),('j','jumboItemCRC')]:
 data=s.league_objectives.background(s,f"/fut/items/images/backgrounds/itembgs/{spec['guid']}/cards_bg_{letter}_1_38_0.dds")
 assert zlib.crc32(data)&0xffffffff==spec[key][0]
assert next(x for x in json.loads(s.league_objectives.tunables(s,b'{"rarities":[]}'))['rarities'] if x['id']==38)['name']=='Prime'
for _ in range(5):
 pack=s.STATE.create_pack(528);assert len(pack['itemData'])==1
 assert pack['itemData'][0]['resourceId']==rid and pack['itemData'][0]['rareflag']==38 and pack['itemData'][0]['untradeable']
status,h,b=s.route_fut('GET',f'/ut/game/fifa21/attributes/metadata?defIds=176635,{rid}',{},b'');assert status==200 and all(x['rating']==89 and x['attributeArray']==m['face'] for x in json.loads(b))
status,h,b=s.route_fut('GET','/ut/game/fifa21/attributes/metadata?defIds=176635',{},b'');assert json.loads(b)[0]['rating']==82
pack=s._owned_reward_pack_json(528,1);assert pack['assetId']==54 and not pack['useDefaultImage'] and pack['name']=='Pack Prime garanti'
config=json.loads((p/'contentfifa/fut/packs/packopening/packopeningconfig.json').read_text());settings=json.loads((p/'contentfifa/fut/packs/packopening/packopeningsetting.json').read_text());row=next(x for x in settings['itemList'] if x['rarity']==38)
assert row['totalRanges']==next(x['totalRanges'] for x in config['rangeValue'] if x['rarity']==38)==3
assert all(len(v)==3 for v in row.values() if isinstance(v,list)) and row['walkOutBucketId']==[1]*3
print('PASS: Ozil Prime89 Arsenal/CAM exact face stats, native stars/attributes, four backgrounds/CRC, Prime label, one-player pack and animation')
