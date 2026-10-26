"""Stable season identity, native claim routes and atomic level receipts."""
import json,re
import season_cosmetics
import season_picks

def normalize(path):
 # FIFA 21 chooses learning/campaign/world from the native group type.
 return re.sub(r'^(/ut/game/fifa21/scmp)/(?:learning|active|world)/(group/)',r'\1/campaign/\2',path)

def _put(s,key,value):
 s.STATE.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))

def window(s):
 with s.STATE.lock:
  data=s.STATE.get('scmp_season_window_v1')
  if not data:
   now=s.now_s();data={'start':now-30*86400,'end':now+365*86400}
   with s.STATE.conn:_put(s,'scmp_season_window_v1',data)
  return data

def chosen_levels(s):
 # CardsDLL 0x331410 consumes scmpChosenRewardDtos, using the level parser
 # at 0x333640 (levelId + integer chosenOption). Preserve the single option 0.
 return [dict(levelId=int(lvl),chosenOption=int((s.STATE.get("scmp_chosen_options",{}) or {}).get(str(lvl),0)),state=2) for lvl in sorted(set(s.STATE.get('scmp_claimed_levels',[]) or []))]

def claim_level(s,lvl,option_id=0):
 with s.STATE.lock:
  xp=int(s.STATE.get('scmp_user_xp',0) or 0)
  claimed=set(s.STATE.get('scmp_claimed_levels',[]) or [])
  level=next((r for r in s._scmp_season_levels() if r['levelId']==lvl),None)
  if level is None or lvl in claimed or xp<level['xpThreshold']:
   return {'awards':[],'awardsList':[],'alreadyClaimed':lvl in claimed,'scmpChosenRewardDtos':chosen_levels(s)}
  option=next((row for row in level['rewardOptionList'] if row['optionId']==option_id),None)
  if option is None:return {'awards':[],'awardsList':[],'invalidOption':True,'scmpChosenRewardDtos':chosen_levels(s)}
  award=option['awards'][0]
  kind=award.get('awardType');items=[]
  pack_id=int(award.get('value',0)) if kind=='pack' else None
  # Preserve existing level rewards while committing their marker with them.
  is_pick=lvl in season_picks.SPECS
  if kind=='item' and not is_pick:resources=[int(award['value'])]
  else:resources=[]
  next_id=max(int(s.STATE.get('next_item_id',900000000000)),int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0) FROM items').fetchone()[0]))
  if is_pick:
   next_id+=1;items.append(season_picks.token(s,lvl,next_id))
  for rid in resources:
   next_id+=1
   items.append(season_cosmetics.item(s,rid,next_id) if rid in season_cosmetics.REWARDS else s.STATE.build_player_item(rid,next_id,'unassigned'))
  with s.STATE.conn:
   if pack_id is not None:
    s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',
      (pack_id,json.dumps({'source':'season_level','levelId':lvl,'created':s.now_s(),'untradeable':True})))
   for item in items:
    s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',(item['id'],item['resourceId'],'unassigned',json.dumps(item)))
   if is_pick:
    token=items[0]
    _put(s,'player_pick:'+str(token['id']),dict(minRating=token['minRating'],choiceCount=token['choiceCount'],choices=[]))
   if items:_put(s,'next_item_id',next_id)
   if kind=='coin':_put(s,'credits',s.STATE.credits()+int(award.get('value',0)))
   chosen=dict(s.STATE.get('scmp_chosen_options',{}) or {});chosen[str(lvl)]=option_id
   _put(s,'scmp_chosen_options',chosen)
   claimed.add(lvl);_put(s,'scmp_claimed_levels',sorted(claimed))
  s.PENDING_USERSESSION_REFRESH.set()
  native=[s._native_pack_item(i) for i in items]
  if is_pick:award=dict(award,itemData=native[0])
  return {'awards':[award],'awardsList':[award],'grantedItems':native,'itemList':native,'alreadyClaimed':False,
          'scmpChosenRewardDtos':chosen_levels(s),'dynamicObjectivesUpdates':{'needsGroupsRefresh':True}}
