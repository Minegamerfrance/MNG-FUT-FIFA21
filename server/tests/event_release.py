"""Release boundaries and native routes, with an isolated club and fake clock."""
import json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/'runtime-source/localfut21'
os.environ['LOCALFUT_RUNTIME_ROOT']=tempfile.mkdtemp(prefix='mng-release-')
os.environ['LOCALFUT21_USER_CONFIG_ROOT']=tempfile.mkdtemp(prefix='mng-release-config-')
sys.path.insert(0,str(p))
import server as s
e=s.event_schedule
rb=next(r for r,m in s.PLAYER_DB.items() if m.get('rareflag')==22)
totw=next(r for r,m in s.PLAYER_DB.items() if m.get('rareflag')==3)
search={'defid':f'{rb},{totw}'}
s.STATE.set('scmp_user_xp',30000)
for now,has_totw,has_rb in [(e.STARTS['totw1']-1,False,False),(e.STARTS['totw1'],True,False),
                            (e.STARTS['rulebreakers']-1,True,False),(e.STARTS['rulebreakers'],True,True)]:
 with patch('event_schedule.time.time',return_value=now):
  flags=s.get_pack_cfg(300)['allowed_rareflags']
  assert (3 in flags)==has_totw and (22 in flags)==has_rb
  assert 21 not in flags and 38 not in flags
  rows=s.fut_inventory.catalogue(s,search,True)
  assert {r['rareflag'] for r in rows}==({3} if has_totw else set())|({22} if has_rb else set())
  categories=s._sbc_sets_response()['categories']
  assert (9 in [r['categoryId'] for r in categories])==has_rb
  assert 3 in [r['categoryId'] for r in categories]
  campaign=s._scmp_campaign_json()
  assert campaign['campaignName']=='Saison des frissons' and len(campaign['levels'])==30
  assert (71 in [r['categoryId'] for r in campaign['categories']])==has_rb
  ads=json.dumps(s.loading_content.content('http://localhost'))
  assert ('rulebreakers-team1.jpg' in ads)==has_rb
  assert ('totw1-new.png' in ads)==has_totw
  assert s.route_fut('GET','/ut/game/fifa21/sbs/setId/910200/challenges',{},b'')[0]==(200 if has_rb else 403)
  for consumer,enabled in [('sqbt',has_rb),('sqbttotw',has_totw)]:
   code,headers,body=s.route_fut('GET','/ut/game/fifa21/featuredsquad/user/stats?featureConsumerId='+consumer,{},b'')
   assert code==200
   assert bool(json.loads(body)['featuredSquadId'])==enabled
  for slot,enabled in [(4,has_totw),(5,has_rb)]:
   assert s.route_fut('GET',f'/ut/game/fifa21/featuredsquad/{slot}',{},b'')[0]==(200 if enabled else 403)
  if not has_rb:
   before=s.STATE.get('scmp_claimed_levels',[])
   assert s.season_persistence.claim_level(s,10)['reason']=='EVENT_NOT_STARTED'
   assert s.STATE.get('scmp_claimed_levels',[])==before
   assert s.route_fut('POST','/ut/game/fifa21/purchased/items',{},b'{"packId":523}')[0]==403
   assert s.route_fut('POST','/ut/game/fifa21/scmp/campaign/group/7101/rewards',{},b'{}')[0]==403
   assert s.route_fut('POST','/ut/game/fifa21/match',{},b'{"featuredSquadId":5}')[0]==403
  else:
   assert s.STATE.create_pack(523)['itemData'][0]['rareflag']==22
   assert s.season_persistence.claim_level(s,10)['grantedItems']
print('PASS: exact Paris launch boundaries, automatic reopening, pack/catalogue gates, hidden ads/SBCs/objectives/featured squads, visible season and delayed event rewards; OTW/Prime remain disabled')
