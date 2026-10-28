from pathlib import Path
import os,sys,tempfile,json
p=Path(__file__).resolve().parents[1]/'runtime-source/localfut21'
w=Path(tempfile.mkdtemp(prefix='mng-ballon-pack-'));os.environ['LOCALFUT_RUNTIME_ROOT']=str(w);os.environ['LOCALFUT21_USER_CONFIG_ROOT']=str(w/'config');sys.path.insert(0,str(p))
import server as s
cfg=s.get_pack_cfg(527);assert cfg['size']==1 and cfg['allowed_rareflags']==[63] and cfg['untradeable']
for _ in range(20):
 pack=s.STATE.create_pack(527);assert len(pack['itemData'])==1
 card=pack['itemData'][0];assert card['rareflag']==63 and card['resourceId'] in cfg['reward_resource_ids'] and card['untradeable'] and not card['loans']
 assert all(not s.PLAYER_DB[r]['packEligible'] for r in cfg['reward_resource_ids'])
assert s._owned_reward_pack_json(527,1)['name']=='Pack Ballon d’Or garanti'
settings=json.loads((p/'contentfifa/fut/packs/packopening/packopeningsetting.json').read_text())
config=json.loads((p/'contentfifa/fut/packs/packopening/packopeningconfig.json').read_text())
row=next(x for x in settings['itemList'] if x['rarity']==63)
assert row['totalRanges']==next(x['totalRanges'] for x in config['rangeValue'] if x['rarity']==63)==3
assert all(len(v)==3 for v in row.values() if isinstance(v,list))
assert set(row['walkOutBucketId'])<=set(x['walkOutBucketId'] for x in settings['walkOutList'])
assert row['tunnelWallGraphicsType']==[3,3,3]
assert row['videoWallBGColor']==['0x14110B']*3 and row['confettiColor1']==['0xFFD700']*3
print('PASS: 20 single untradeable rarity63 openings, objective players excluded from other packs, native gold walkout settings with valid buckets/ranges')
