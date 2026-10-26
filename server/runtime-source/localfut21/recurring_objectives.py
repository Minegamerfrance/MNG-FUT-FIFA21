"""Paris-calendar daily/weekly objectives with once-only events and rewards."""
import hashlib,json,re,uuid
from datetime import datetime,timedelta,timezone
import squad_battles_weekly as weekly

CATEGORY=1
PENDING='mng_recurring_match_v1'
BASELINE='mng_recurring_sbc_baseline_v1'
GROUPS={
 8001:dict(title='Objectifs quotidiens',period='daily',xp=25,pack=521,
  challenges=[('Connexion FUT','Connectez-vous à FUT.','login',1),
              ('Défis quotidiens','Terminez 5 SBC.','sbc',5),
              ('Sur le terrain','Disputez 3 matchs FUT.','matches',3),
              ('Victoires quotidiennes','Remportez 5 matchs FUT.','wins',5)]),
 8002:dict(title='Objectifs hebdomadaires',period='weekly',xp=100,pack=524,
  challenges=[('Semaine de football','Disputez 10 matchs FUT.','matches',10),
              ('Série de victoires','Remportez 10 matchs FUT.','wins',10),
              ('Passeurs décisifs','Adressez 20 passes décisives dans des matchs FUT.','assists',20),
              ('Buteurs de la semaine','Marquez 20 buts dans des matchs FUT.','goals',20),
              ('Défis de la semaine','Terminez 15 SBC.','sbc',15)])}

def window(timestamp,period):
 if period=='weekly':return weekly.window(timestamp)
 utc=datetime.fromtimestamp(timestamp,timezone.utc)
 wall=(utc+timedelta(hours=weekly._offset(utc))).replace(hour=0,minute=0,second=0,microsecond=0)
 def convert(local):
  candidate=local-timedelta(hours=1)
  return int((local-timedelta(hours=weekly._offset(candidate))).timestamp())
 return convert(wall),convert(wall+timedelta(days=1))

def _put(s,key,value):
 s.STATE.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))

def initialize(s):
 with s.STATE.lock:
  if s.STATE.get(BASELINE) is None:
   with s.STATE.conn:_put(s,BASELINE,s.STATE.get('sbc_completed',[]) or [])

def progress(s,gid,now=None):
 start,end=window(s.now_s() if now is None else now,GROUPS[gid]['period'])
 key=f'mng_recurring_{gid}_{start}'
 return key,s.STATE.get(key,{'totals':{},'claimedObjectives':[],'claimed':False}),start,end

def _event(s,identifier,increments,now=None,pending_clear=False):
 now=s.now_s() if now is None else now
 receipt='mng_recurring_event_'+hashlib.sha256(identifier.encode()).hexdigest()
 with s.STATE.lock:
  if s.STATE.get(receipt):return False
  with s.STATE.conn:
   for gid in GROUPS:
    key,p,_,_=progress(s,gid,now)
    for metric,amount in increments.items():
     p['totals'][metric]=int(p['totals'].get(metric,0))+max(0,int(amount))
    _put(s,key,p)
   _put(s,receipt,{'event':identifier,'time':now})
   if pending_clear:_put(s,PENDING,None)
 return True

def login(s):
 cycle,_=window(s.now_s(),'daily')
 _event(s,'login:'+str(cycle),{'login':1})

def award_xp(amount):
 return dict(type='xp',awardType='xp',value=amount,awardValue=amount,count=1,awardCount=1,
             halId=0,assetId=0,isUntradeable=True,untradeable=True)

def pack_award(s,pid):
 result=s._pack_award(pid)
 name=s.get_pack_cfg(pid)['name']
 for key in ('name','packName','packs','AWD_PACKS_STRING'):result[key]=name
 return result

def group(s,gid):
 spec=GROUPS[gid];_,p,start,end=progress(s,gid)
 rows=spec['challenges'];totals=p['totals'];taken=p['claimedObjectives']
 completed=sum(int(totals.get(metric,0))>=target for _,_,metric,target in rows)
 objectives=[]
 for i,(title,desc,metric,target) in enumerate(rows):
  actual=min(target,int(totals.get(metric,0)))
  rewards=[award_xp(spec['xp'])]
  objectives.append(dict(id=gid*100+i+1,objectiveId=gid*100+i+1,name=title,description=desc,
   multiplier=target,priority=i+1,currentProgress=actual,progressCount=actual,progress=actual,target=target,targetValue=target,
   ruleTargetValue=target,ruleDto=[dict(ruleTargetValue=target,ruleOperator='MORE_OR_EQUAL')],
   state='REDEEMED' if i in taken else 'COMPLETED' if actual>=target else 'IN_PROGRESS',
   awards=rewards,awardsList=rewards,xp=spec['xp'],xpReward=spec['xp'],takeMeThereLink='',isWeb=False))
 state=4 if p['claimed'] else 2 if completed==len(rows) else 1
 return dict(groupId=gid,id=gid,groupType=0,groupState=state,state=state,
  priority=gid-8000,title=spec['title'],subTitle='Renouvellement à minuit · heure française' if spec['period']=='daily' else 'Renouvellement dimanche à 10 h · heure française',
  startTime=start,endTime=end,visibilityTime=start,objectivesNumber=len(rows),objectivesCount=len(rows),
  objectivesCompleted=completed,groupIdsToUnlock=[],subGroupType=0,subGroupTypeAttribute=0,
  awardsList=[pack_award(s,spec['pack'])],rewardOptionList=[],objectives=objectives)

def category(s):
 groups=[group(s,gid) for gid in GROUPS]
 return dict(categoryId=CATEGORY,id=CATEGORY,name='Objectifs',priority=2,groupsList=groups,groups=groups)

def claim(s,gid,index=None):
 with s.STATE.lock:
  spec=GROUPS[gid];key,p,_,_=progress(s,gid);rows=spec['challenges']
  if index is not None and not 0<=index<len(rows):return 404,{'reason':'UNKNOWN_OBJECTIVE'}
  if (p['claimed'] if index is None else index in p['claimedObjectives']):
   return 200,dict(alreadyClaimed=True,awards=[],awardsList=[],itemList=[],grantedItems=[],xpAward=0)
  needed=range(len(rows)) if index is None else [index]
  if any(int(p['totals'].get(rows[i][2],0))<rows[i][3] for i in needed):
   return 403,{'reason':'OBJECTIVES_INCOMPLETE','awards':[],'itemList':[]}
  newly_taken=[i for i in needed if i not in p['claimedObjectives']]
  amount=len(newly_taken)*spec['xp']
  xp=int(s.STATE.get('scmp_user_xp',0) or 0)+amount
  rewards=[award_xp(amount)] if amount else []
  p['claimedObjectives']=sorted(set(p['claimedObjectives'])|set(newly_taken))
  if index is None:
   p['claimed']=True;rewards.insert(0,pack_award(s,spec['pack']))
  with s.STATE.conn:
   if index is None:
    s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',
     (spec['pack'],json.dumps({'source':'recurring_objectives','groupId':gid,'period':key,'untradeable':True,'created':s.now_s()})))
   _put(s,'scmp_user_xp',xp);_put(s,key,p)
  s.PENDING_USERSESSION_REFRESH.set()
  return 200,dict(alreadyClaimed=False,awards=rewards,awardsList=rewards,itemList=[],grantedItems=[],xpAward=amount,userXp=xp,
                  preOrderPacks=len(s.STATE.unopened_pack_ids()),unopenedPacks=len(s.STATE.unopened_pack_ids()))

def route(s,method,path):
 if re.fullmatch(r'/ut/game/fifa21/scmp/(?:active|learning)/category/1/details',path):
  return 200,dict(categoryId=1,groupsList=category(s)['groupsList'])
 m=re.fullmatch(r'/ut/game/fifa21/scmp/campaign/group/(\d+)(?:/objective/(\d+))?/rewards',path)
 if m and method in ('PUT','POST'):
  gid=int(m.group(1))
  if gid==1:return 404,{'reason':'REMOVED_OBJECTIVE_GROUP'}
  if gid in GROUPS:return claim(s,gid,int(m.group(2))-gid*100-1 if m.group(2) else None)
 return None

def _positive(value):
 return min(1000,max(0,value)) if type(value) is int else 0

def start(s,response):
 if not isinstance(response,dict):return
 squad=response.get('squad',{})
 if not isinstance(squad,dict):return
 players=[slot.get('itemData',{}) for slot in squad.get('players',[]) if isinstance(slot,dict)]
 players=[p for p in players if p.get('id') and not p.get('dream') and not p.get('concept')]
 if len(players)<11:return
 with s.STATE.lock:
  context=s.STATE.get(s.squad_battles_results.CONTEXT,{}) if s.STATE.get('mng_active_match_mode')=='squad_battles' else {}
  native_id=context.get('id') if isinstance(context,dict) else None
  previous=s.STATE.get(PENDING)
  if previous and previous.get('nativeId')==native_id:return
  with s.STATE.conn:
   _put(s,PENDING,dict(id=uuid.uuid4().hex,nativeId=native_id,started=s.now_s(),players=[
    dict(id=p['id'],assetId=p.get('assetId'),resourceId=p.get('resourceId')) for p in players]))

def finish(s,payload):
 if not isinstance(payload,dict):return
 with s.STATE.lock:
  pending=s.STATE.get(PENDING)
  if not pending:return
  reason=str(payload.get('endReason','')).upper()
  if reason not in ('WIN','DRAW','LOSS'):
   with s.STATE.conn:_put(s,PENDING,None)
   return
  ids={p['id'] for p in pending['players']}
  assets={p[k] for p in pending['players'] for k in ('assetId','resourceId') if p.get(k)}
  stats={i['id']:i for i in payload.get('items',[]) if isinstance(i,dict) and i.get('id') in ids}
  goals=sum(_positive(i.get('goals')) for i in stats.values())
  assists=sum(_positive(i.get('assists')) for i in stats.values())
  # Native results contain local item deltas; event rows are a fallback.
  if not any('goals' in i for i in stats.values()) or not any('assists' in i for i in stats.values()):
   event_totals={'goal':0,'assist':0}
   for event in payload.get('events',[]):
    attrs=event.get('attributes',[]) if isinstance(event,dict) else []
    entry={a.get('key'):a.get('value') for a in attrs if isinstance(a,dict)} if isinstance(attrs,list) else {}
    if entry.get('player_id') in assets and entry.get('name') in event_totals:event_totals[entry['name']]+=1
   if not any('goals' in i for i in stats.values()):goals=event_totals['goal']
   if not any('assists' in i for i in stats.values()):assists=event_totals['assist']
  report=payload.get('matchReportId')
  identifier='match:'+str(report) if report and str(report).strip('0') else 'match:'+pending['id']
  recorded=_event(s,identifier,dict(matches=1,wins=int(reason=='WIN'),goals=goals,assists=assists),pending_clear=True)
  if not recorded:
   with s.STATE.conn:_put(s,PENDING,None)

def observe(s,method,path,request,response):
 if path=='/ut/auth' and method!='DELETE':login(s)
 if path=='/ut/game/fifa21/match' and method in ('PUT','POST'):start(s,response)
 if path=='/ut/game/fifa21/match/end' and method in ('PUT','POST'):finish(s,request)
 m=re.fullmatch(r'/ut/game/fifa21/sbs/challenge/(\d+)',path)
 if m and method=='PUT' and isinstance(response,dict) and response.get('success') and response.get('completed'):
  challenge=s._SBC_CHAL_BY_INT.get(int(m.group(1)))
  if challenge and str(challenge['id']) not in set(s.STATE.get(BASELINE,[]) or []):
   _event(s,'sbc:'+str(challenge['id']),{'sbc':1})
