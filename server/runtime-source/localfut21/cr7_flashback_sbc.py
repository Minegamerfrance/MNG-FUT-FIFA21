import remote_assets
"""Owned-card exchanges for CR7 Flashback and Day of the Dead."""
import json
import re
import rulebreakers_sbc

PLAYER=83906881
PREFIX='cr7_flashback_sbc_'
RULES={
 910201:dict(rating=80,chemistry=80,league=308,leagueCount=1,totw=1),
 910202:dict(rating=81,chemistry=65,league=308,leagueCount=1),
 910203:dict(rating=82,chemistry=70,league=308,leagueCount=1,club=11,clubCount=1),
 910204:dict(rating=84,chemistry=75,club=11,clubCount=1,totw=1),
 910205:dict(rating=85,chemistry=75,club=11,clubCount=2,totw=1),
 910206:dict(rating=86,chemistry=65,league=13,leagueCount=1),
 910301:dict(rating=83,chemistry=65),
}
RULES.update({910401: {'rating': 83, 'chemistry': 80, 'club': 112172, 'clubCount': 3}, 910402: {'rating': 84, 'chemistry': 75, 'league': 19, 'leagueCount': 1}, 910403: {'rating': 85, 'chemistry': 70, 'club': 21, 'clubCount': 1, 'totw': 1}, 910404: {'rating': 85, 'chemistry': 65, 'league': 19, 'leagueCount': 1}, 910405: {'rating': 86, 'chemistry': 60, 'club': 21, 'clubCount': 1, 'totw': 1}, 910406: {'rating': 86, 'chemistry': 55, 'league': 19, 'leagueCount': 1}})
GROUP_PLAYERS={910200:PLAYER,910400:67321486}

def asset(s,method,path):
 name=path.rsplit('/',1)[-1]
 if path in ('/fut/sbc/gen4/sets/images/sbc_set_image_1010002.png','/fut/sbc/gen4/challenges/images/sbc_set_image_1010002.png'):
  return 200,{'Content-Type':'image/png','Cache-Control':'no-store'},remote_assets.read((s.ROOT/'assets/sbc'/name))
 # A fresh native image identity avoids reusing the prior failed fetch.
 if path in ('/fut/sbc/gen4/sets/images/sbc_set_image_1011007.png',
             '/fut/sbc/gen4/challenges/images/sbc_set_image_1011007.png'):
  return 200,{'Content-Type':'image/png','Cache-Control':'no-store'},remote_assets.read((s.ROOT/'assets/sbc/sbc_set_image_1010007.png'))
 if path not in ('/fut/sbc/gen4/sets/images/sbc_set_image_1010007.png',
                 '/fut/sbc/gen4/challenges/images/sbc_set_image_1010007.png',
                 '/fut/sbc/gen4/sets/images/sbc_set_image_1010006.png'):return None
 return 200,{'Content-Type':'image/png','Cache-Control':'no-store'},remote_assets.read((s.ROOT/'assets/sbc'/name))

def selected(s,cid):
 return [(slot['index'],item) for slot in s.STATE.get(PREFIX+'squad_'+str(cid),[])
         for item in [s.STATE.get_item(slot['itemId'])] if item]

def view(s,cid):
 result=s._sbc_empty_squad(cid);pairs=selected(s,cid)
 result['squad'].update(players=[dict(index=i,itemData=s._native_player_item(item)) for i,item in pairs],
                       rating=rulebreakers_sbc.rating([x for _,x in pairs]))
 return result

def save(s,cid,payload):
 if not isinstance(payload,dict):return 400,dict(reason='INVALID_SQUAD')
 document=payload.get('squad',payload)
 if not isinstance(document,dict):return 400,dict(reason='INVALID_SQUAD')
 raw=document.get('players',[])
 if not isinstance(raw,list):return 400,dict(reason='INVALID_SQUAD')
 slots=[];seen=set();positions=set()
 for fallback,entry in enumerate(raw):
  if not isinstance(entry,dict):return 400,dict(reason='INVALID_PLAYER')
  item=entry.get('itemData',entry)
  if not isinstance(item,dict):return 400,dict(reason='INVALID_PLAYER')
  index=entry.get('index',fallback);iid=item.get('id',entry.get('itemId',0))
  if not iid:continue
  if type(iid) is not int or type(index) is not int or not 0<=index<11 or iid in seen or index in positions:
   return 400,dict(reason='INVALID_SQUAD_SLOTS')
  seen.add(iid);positions.add(index);slots.append(dict(index=index,itemId=iid))
 with s.STATE.lock:s.STATE.set(PREFIX+'squad_'+str(cid),slots)
 return 200,{}

def submit(s,cid):
 with s.STATE.lock:
  receipt=PREFIX+'receipt_'+str(cid);previous=s.STATE.get(receipt)
  if previous:return 200,previous
  challenge=s._SBC_CHAL_BY_INT[cid];set_id=challenge['_setInt'];group=s._SBC_SET_BY_INT[set_id]
  pairs=selected(s,cid);items=[x for _,x in pairs];rules=RULES[cid]
  def invalid(message):return 200,dict(id=cid,challengeId=cid,setId=set_id,success=False,valid=False,completed=False,status='INVALID',message=message)
  if len(items)!=11:return invalid('11 joueurs possédés sont nécessaires.')
  if any(x.get('itemType','player')!='player' or x.get('concept') or x.get('dream') or int(x.get('loans',0) or 0)>0 for x in items):
   return invalid('Les joueurs de prêt et concepts ne peuvent pas être échangés.')
  if len({int(x.get('assetId',x['resourceId'])) for x in items})!=11:return invalid('Les 11 joueurs doivent être différents.')
  if rulebreakers_sbc.rating(items)<rules['rating']:return invalid(f"Note d’équipe minimale : {rules['rating']}.")
  if sum(int(x.get('rareflag',0))==3 for x in items)<rules.get('totw',0):return invalid('Au moins un joueur TOTW est obligatoire.')
  if sum(int(x.get('leagueId',0))==rules.get('league') for x in items)<rules.get('leagueCount',0):return invalid('Le nombre de joueurs du championnat requis est insuffisant.')
  if sum(int(x.get('teamid',0))==rules.get('club') for x in items)<rules.get('clubCount',0):return invalid('Le nombre de joueurs du club requis est insuffisant.')
  # Chemistry is evaluated by FIFA's native SBC eligibility rules, as for the
  # other authored SBCs. Never substitute a guessed server chemistry formula.
  ids={int(x['id']) for x in items}
  for iid in ids:
   row=s.STATE.conn.execute('SELECT pile FROM items WHERE id=?',(iid,)).fetchone()
   if not row or row[0] not in ('club','unassigned','squad'):return invalid('Un joueur sélectionné n’est plus disponible.')
  done=s._sbc_completed();done.add(str(challenge['id']))
  complete=all(str(c['id']) in done for c in group['challenges'])
  entries=challenge['rewards']['entries']
  pack_ids=[s._sbc_pack_id(e['attributes']['pack'],challenge) for e in entries if e['type']=='PACK']
  assert len(pack_ids)==1
  item=None;granted=[]
  reward_player=GROUP_PLAYERS.get(set_id)
  if reward_player and complete:
   identifier=max(int(s.STATE.get('next_item_id',900000000000))+1,int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM items').fetchone()[0]))
   item=s.STATE.build_player_item(reward_player,identifier,'unassigned');item.update(untradeable=True,untradeableCount=1,discardValue=0,objectiveReward=False)
   granted=[s._native_player_item(item)]
  pack_count=len(s.STATE.unopened_pack_ids())+len(pack_ids)
  response=dict(id=cid,challengeId=cid,setId=set_id,success=True,valid=True,completed=True,status='COMPLETED',timesCompleted=1,
   grantedChallengeAwards=s._sbc_awards(challenge),grantedSetAwards=s._sbc_awards(group) if complete else [],
   awards=[],rewards=[],credits=s.STATE.credits(),grantedItemsCount=len(granted),grantedItems=granted,itemData=granted,
   preOrderPacks=pack_count,recoveredPacks=0,unopenedPacks=pack_count)
  with s.STATE.conn:
   for iid in ids:s.STATE.conn.execute('DELETE FROM items WHERE id=?',(iid,))
   for row in s.STATE.conn.execute('SELECT id,data FROM squads').fetchall():
    squad=json.loads(row['data']);old=squad.get('players',[])
    def iid(slot):return slot.get('itemId',slot.get('itemData',{}).get('id',slot.get('id',0))) if isinstance(slot,dict) else 0
    kept=[slot for slot in old if iid(slot) not in ids]
    if kept!=old:
     squad['players']=kept
     if squad.get('captain') in ids:squad['captain']=0
     squad['kicktakers']=[x for x in squad.get('kicktakers',[]) if iid(x) not in ids]
     s.STATE.conn.execute('UPDATE squads SET data=? WHERE id=?',(json.dumps(squad),row['id']))
   for pid in pack_ids:
    s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',(pid,json.dumps(dict(source='kimmich_rulebreakers_sbc' if set_id==910400 else 'cr7_flashback_sbc' if set_id==910200 else 'day_of_dead_sbc',challengeId=cid,created=s.now_s(),untradeable=False))))
   if item:
    s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',(identifier,reward_player,'unassigned',json.dumps(item)))
    rulebreakers_sbc._put(s,'next_item_id',identifier)
   rulebreakers_sbc._put(s,'sbc_completed',sorted(done))
   rulebreakers_sbc._put(s,PREFIX+'squad_'+str(cid),[])
   rulebreakers_sbc._put(s,receipt,response)
  s.PENDING_USERSESSION_REFRESH.set()
  return 200,response

def route(s,method,path,payload):
 match=re.fullmatch(r'/ut/game/fifa21/sbs/challenge/(91020[1-6]|910301|91040[1-6])(/squad)?',path)
 if not match:return None
 cid=int(match.group(1))
 if match.group(2) and method=='PUT':return save(s,cid,payload)
 if not match.group(2) and method=='PUT':return submit(s,cid)
 return 200,view(s,cid)
