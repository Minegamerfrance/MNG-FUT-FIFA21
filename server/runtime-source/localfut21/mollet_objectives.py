"""Mollet Ligue 1 objectives and transactional, once-only rewards."""
import json
import re
import uuid

GROUP=7005
PLAYER=84095368
KEY='league_mollet_v2'
XP=250
CHALLENGES=(
    ('Victoires en Ligue 1',15,520,'Remportez 15 matchs en Clashs d’équipes ou Rivals avec uniquement des joueurs de Ligue 1 parmi les 11 titulaires.'),
    ('Soif de buts',30,521,'Marquez 30 buts avec des joueurs de Ligue 1 en Clashs d’équipes ou Rivals.'),
    ('Altruiste par excellence',20,521,'Adressez 20 passes décisives avec des joueurs de Ligue 1 en Clashs d’équipes ou Rivals.'),
    ('Tout en finesse',6,522,'Marquez au moins un but en finesse avec un joueur de Ligue 1 dans 6 matchs distincts en Clashs d’équipes ou Rivals.'),
    ('La Ligue 1 en force',4,522,'Marquez au moins un but hors de la surface avec un joueur de Ligue 1 dans 4 matchs distincts en Clashs d’équipes ou Rivals.'),
)

def progress(s):
    p=s.STATE.get(KEY,{}) or {}
    if not p:
        old=s.STATE.get('league_mollet_v1',{}) or {}
        p={'counts':[0]*5,'claimedObjectives':[]}
        if old.get('claimed'):
            p.update(claimed=True,counts=[r[1] for r in CHALLENGES],claimedObjectives=list(range(5)))
    return p

def xp_award():
    return dict(type='xp',awardType='xp',value=XP,awardValue=XP,count=1,awardCount=1,
                halId=0,assetId=0,untradeable=True,isUntradeable=True)

def objective_awards(s,index):
    pack=s._pack_award(CHALLENGES[index][2]);pack['halId']=pack['assetId']
    return [pack,xp_award()]

def group(s,details=True):
    p=progress(s);counts=p['counts'];claimed=bool(p.get('claimed'))
    done=all(counts[i]>=r[1] for i,r in enumerate(CHALLENGES))
    state=4 if claimed else 2 if done else 1
    result=dict(groupId=GROUP,id=GROUP,groupType=0,groupState=state,state=state,priority=5,
        title='Joueur de Ligue 1',subTitle='Ligue 1 · Clashs d’équipes et Rivals',
        startTime=0,endTime=2145916800,visibilityTime=0,objectivesNumber=5,objectivesCount=5,
        objectivesCompleted=sum(counts[i]>=r[1] for i,r in enumerate(CHALLENGES)),
        groupIdsToUnlock=[],subGroupType=0,subGroupTypeAttribute=0,
        awardsList=[s._scmp_award('player',PLAYER),xp_award()],rewardOptionList=[])
    if details:
        result['objectives']=[]
        for i,(title,target,_,description) in enumerate(CHALLENGES):
            actual=min(target,counts[i]);taken=i in p.get('claimedObjectives',[])
            rewards=objective_awards(s,i)
            result['objectives'].append(dict(objectiveId=GROUP*100+i+1,id=GROUP*100+i+1,
                name=title,description=description,multiplier=target,priority=i+1,
                currentProgress=actual,progressCount=actual,progress=actual,target=target,targetValue=target,ruleTargetValue=target,
                ruleDto=[dict(ruleTargetValue=target,ruleOperator='MORE_OR_EQUAL')],
                state='REDEEMED' if taken else 'COMPLETED' if actual>=target else 'IN_PROGRESS',
                takeMeThereLink='',isWeb=False,awards=rewards,awardsList=rewards,xp=XP,xpReward=XP))
    return result

def _put(s,key,value):
    s.STATE.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))

def claim(s,index=None):
    with s.STATE.lock:
        p=progress(s)
        taken=p.get('claimed') if index is None else index in p.get('claimedObjectives',[])
        if taken:return 200,dict(alreadyClaimed=True,awards=[],awardsList=[],itemList=[],grantedItems=[],xpAward=0)
        if index is None:
            complete=all(p['counts'][i]>=r[1] for i,r in enumerate(CHALLENGES))
        else:complete=p['counts'][index]>=CHALLENGES[index][1]
        if not complete:return 403,dict(reason='OBJECTIVES_INCOMPLETE',awards=[],itemList=[])
        xp=int(s.STATE.get('scmp_user_xp',0) or 0)+XP
        items=[]
        if index is None:
            identifier=max(int(s.STATE.get('next_item_id',900000000000))+1,
                int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM items').fetchone()[0]))
            item=s.STATE.build_player_item(PLAYER,identifier,'unassigned')
            item.update(untradeable=True,untradeableCount=1,objectiveReward=True)
            items=[item];p['claimed']=True
            awards=[s._scmp_award('player',PLAYER),xp_award()]
        else:
            p['claimedObjectives']=sorted(set(p.get('claimedObjectives',[]))|{index})
            awards=objective_awards(s,index)
        # Pack/card, XP and receipt share one commit; retries cannot pay twice.
        with s.STATE.conn:
            if index is None:
                s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',
                    (identifier,PLAYER,'unassigned',json.dumps(items[0])))
                _put(s,'next_item_id',identifier)
            else:
                s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',
                    (CHALLENGES[index][2],json.dumps({'source':'mollet_objective','objectiveId':GROUP*100+index+1,'created':s.now_s(),'untradeable':True})))
            _put(s,'scmp_user_xp',xp);_put(s,KEY,p)
        native=[s._native_pack_item(item) for item in items]
        s.PENDING_USERSESSION_REFRESH.set()
        return 200,dict(alreadyClaimed=False,awards=awards,awardsList=awards,itemList=native,
                        grantedItems=native,xpAward=XP,userXp=xp)

def route(s,method,path):
    m=re.fullmatch(r'/ut/game/fifa21/scmp/campaign/group/7005(?:/objective/(\d+))?/rewards',path)
    if not m or method not in ('POST','PUT'):return None
    index=int(m.group(1))-GROUP*100-1 if m.group(1) else None
    if index is not None and index not in range(5):return 404,{'reason':'UNKNOWN_OBJECTIVE'}
    return claim(s,index)

def reset(s):
    with s.STATE.lock:
        p=progress(s)
        if p.pop('pending',None) is not None:s.STATE.set(KEY,p)

def mode(s,payload):
    active=s.STATE.get('mng_active_match_mode','')
    if active=='squad_battles':return active
    if active in ('rivals','division_rivals'):return 'rivals'
    if any(str(payload.get(k,'')).upper() in ('RIVALS','DIVISION_RIVALS') for k in ('gameMode','mode','matchType','type')):return 'rivals'
    slot=payload.get('sqbtOpponentSquadId')
    if type(slot) is int and 0<=slot<=3:return 'squad_battles'
    return None

def start(s,payload,response):
    with s.STATE.lock:
        p=progress(s)
        if p.get('claimed'):return
        if p.get('pending'):return  # repeated match preparation, not a second match
        snapshot=[]
        for slot in response.get('squad',{}).get('players',[]):
            item=slot.get('itemData') or {}
            if item.get('dream') or item.get('concept'):continue
            card=s.PLAYER_DB.get(int(item.get('resourceId',0)))
            if card:
                snapshot.append(dict(id=int(item.get('id',0)),resourceId=int(item['resourceId']),
                    assetId=int(card.get('assetId',item['resourceId'])),leagueId=int(card.get('leagueId',0)),index=int(slot.get('index',99))))
        p['pending']=dict(id=uuid.uuid4().hex,mode=mode(s,payload),players=snapshot)
        s.STATE.set(KEY,p)

def _positive(value):
    return max(0,value) if type(value) is int else 0

def finish(s,payload):
    with s.STATE.lock:
        p=progress(s);context=p.pop('pending',None)
        if not context:return
        if context['mode'] not in ('squad_battles','rivals') or payload.get('endReason','').upper() not in ('WIN','DRAW','LOSS'):
            s.STATE.set(KEY,p);return
        players=context['players'];ligue=[x for x in players if x['leagueId']==16]
        ids={x['id'] for x in ligue if x['id']>0}
        assets={x['assetId'] for x in ligue}|{x['resourceId'] for x in ligue}
        starters=[x for x in players if x['index']<11]
        wins=int(payload.get('endReason')=='WIN' and len(starters)==11 and all(x['leagueId']==16 for x in starters))
        items=payload.get('items',[])
        stats=[x for x in items if isinstance(x,dict) and x.get('id') in ids] if isinstance(items,list) else []
        goals=sum(_positive(x.get('goals')) for x in stats)
        assists=sum(_positive(x.get('assists')) for x in stats)
        events=[]
        for event in payload.get('events',[]) if isinstance(payload.get('events'),list) else []:
            if not isinstance(event,dict):continue
            attrs=event.get('attributes',[])
            if not isinstance(attrs,list):continue
            fields={x.get('key'):x.get('value') for x in attrs if isinstance(x,dict) and x.get('key')!='flag'}
            if fields.get('player_id') not in assets:continue
            flags=[x.get('value') for x in attrs if isinstance(x,dict) and x.get('key')=='flag']
            events.append(dict(name=fields.get('name'),flags=flags,fields=fields))
        if not stats:
            goals=sum(e['name']=='goal' for e in events)
            assists=sum(e['name']=='assist' for e in events)
        config_path=s.ROOT/'mollet-event-flags.json'
        config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
        def special(event,kind):
            if event['name']!='goal':return False
            explicit={'finesse':('was_finesse','finesse'),'outsideBox':('fromOutsideBox','outsideBox')}[kind]
            return (any(event['fields'].get(k) is True or event['fields'].get(k)==1 for k in explicit)
                or any(flag in config.get(kind,[]) for flag in event['flags']))
        changes=[wins,goals,assists,int(any(special(e,'finesse') for e in events)),int(any(special(e,'outsideBox') for e in events))]
        p['counts']=[min(row[1],p['counts'][i]+changes[i]) for i,row in enumerate(CHALLENGES)]
        # Retain real flags so the two shot classifiers can be calibrated later
        # without inventing progress or losing goals from completed matches.
        audit=dict(id=context['id'],mode=context['mode'],increments=changes,events=events,at=s.now_s())
        with s.STATE.conn:
            _put(s,'league_mollet_match_'+context['id'],audit);_put(s,KEY,p)
        s.log.info('MOLLET match=%s increments=%s',context['id'],changes)
