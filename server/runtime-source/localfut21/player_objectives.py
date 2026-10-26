"""League and event campaigns with match snapshots and atomic reward receipts."""
import json
import uuid
import mollet_objectives

class Campaign:
    def __init__(self, gid, spec, rows, xp=250, group_xp=250, event=False):
        self.gid,self.spec,self.rows=gid,spec,rows
        self.xp,self.group_xp,self.event=xp,group_xp,event
        self.key=spec['key']

    def progress(self,s):
        p=s.STATE.get(self.key,{}) or {}
        if not p:
            old=s.STATE.get(self.spec.get('oldKey',''),{}) or {}
            p=dict(counts=[0]*len(self.rows),claimedObjectives=[])
            if old.get('claimed'):
                p.update(claimed=True,counts=[r[1] for r in self.rows],claimedObjectives=list(range(len(self.rows))))
        return p

    def xp_award(self,amount):
        return dict(type='xp',awardType='xp',value=amount,awardValue=amount,count=1,awardCount=1,
                    halId=0,assetId=0,untradeable=True,isUntradeable=True)

    def awards(self,s,index=None):
        if index is None:
            reward=s._scmp_award('player',self.spec['player'])
        else:
            reward=s._pack_award(self.rows[index][2]);reward['halId']=reward['assetId']
        return [reward,self.xp_award(self.group_xp if index is None else self.xp)]

    def group(self,s,details=True):
        p=self.progress(s);counts=p['counts'];claimed=bool(p.get('claimed'))
        completed=sum(counts[i]>=row[1] for i,row in enumerate(self.rows))
        state=4 if claimed else 2 if completed==len(self.rows) else 1
        result=dict(groupId=self.gid,id=self.gid,groupType=0,groupState=state,state=state,
            priority=self.spec.get('priority',self.gid),title=self.spec['title'],
            subTitle=self.spec.get('subTitle',self.spec['leagueName']+' · Clashs d’équipes et Rivals'),startTime=0,
            endTime=2145916800,visibilityTime=0,objectivesNumber=len(self.rows),objectivesCount=len(self.rows),
            objectivesCompleted=completed,groupIdsToUnlock=[],subGroupType=0,subGroupTypeAttribute=0,
            awardsList=self.awards(s),rewardOptionList=[])
        if details:
            result['objectives']=[]
            order=self.spec.get('displayOrder',list(range(len(self.rows))))
            for rank,i in enumerate(order):
                title,target,_,description=self.rows[i]
                actual=min(target,counts[i]);taken=i in p.get('claimedObjectives',[])
                rewards=self.awards(s,i)
                result['objectives'].append(dict(objectiveId=self.gid*100+i+1,id=self.gid*100+i+1,
                    name=title,description=description,multiplier=target,priority=len(self.rows)-rank if 'displayOrder' in self.spec else i+1,currentProgress=actual,progressCount=actual,
                    progress=actual,target=target,targetValue=target,ruleTargetValue=target,
                    ruleDto=[dict(ruleTargetValue=target,ruleOperator='MORE_OR_EQUAL')],
                    state='REDEEMED' if taken else 'COMPLETED' if actual>=target else 'IN_PROGRESS',
                    takeMeThereLink='',isWeb=False,awards=rewards,awardsList=rewards,xp=self.xp,xpReward=self.xp))
        return result

    def claim(self,s,index=None):
        with s.STATE.lock:
            p=self.progress(s)
            if p.get('claimed') if index is None else index in p.get('claimedObjectives',[]):
                return 200,dict(alreadyClaimed=True,awards=[],awardsList=[],itemList=[],grantedItems=[],xpAward=0)
            complete=all(p['counts'][i]>=r[1] for i,r in enumerate(self.rows)) if index is None else p['counts'][index]>=self.rows[index][1]
            if not complete:return 403,dict(reason='OBJECTIVES_INCOMPLETE',awards=[],itemList=[])
            amount=self.group_xp if index is None else self.xp
            xp=int(s.STATE.get('scmp_user_xp',0) or 0)+amount
            items=[]
            if index is None:
                identifier=max(int(s.STATE.get('next_item_id',900000000000))+1,
                    int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM items').fetchone()[0]))
                item=s.STATE.build_player_item(self.spec['player'],identifier,'unassigned')
                item.update(untradeable=True,untradeableCount=1,objectiveReward=True)
                items=[item];p['claimed']=True
            else:p['claimedObjectives']=sorted(set(p.get('claimedObjectives',[]))|{index})
            with s.STATE.conn:
                if index is None:
                    s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',
                        (identifier,self.spec['player'],'unassigned',json.dumps(items[0])))
                    mollet_objectives._put(s,'next_item_id',identifier)
                else:
                    s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',
                        (self.rows[index][2],json.dumps(dict(source='player_objective',objectiveId=self.gid*100+index+1,created=s.now_s(),untradeable=True))))
                mollet_objectives._put(s,'scmp_user_xp',xp);mollet_objectives._put(s,self.key,p)
            native=[s._native_pack_item(item) for item in items]
            s.PENDING_USERSESSION_REFRESH.set()
            return 200,dict(alreadyClaimed=False,awards=self.awards(s,index),awardsList=self.awards(s,index),
                itemList=native,grantedItems=native,xpAward=amount,userXp=xp)

    def reset(self,s):
        with s.STATE.lock:
            p=self.progress(s)
            if p.pop('pending',None) is not None:s.STATE.set(self.key,p)

    def start(self,s,payload,response):
        with s.STATE.lock:
            p=self.progress(s)
            if p.get('claimed') or p.get('pending'):return
            players=[]
            for slot in response.get('squad',{}).get('players',[]):
                item=slot.get('itemData') or {}
                if item.get('dream') or item.get('concept'):continue
                card=s.PLAYER_DB.get(int(item.get('resourceId',0)))
                if card:
                    players.append(dict(id=int(item.get('id',0)),resourceId=int(item['resourceId']),
                        assetId=int(card.get('assetId',item['resourceId'])),leagueId=int(card.get('leagueId',0)),
                        nation=int(card.get('nation',0)),club=int(card.get('teamid',0)),
                        position=str(item.get('preferredPosition') or card.get('preferredPosition','')).upper(),index=int(slot.get('index',99))))
            p['pending']=dict(id=uuid.uuid4().hex,mode=mollet_objectives.mode(s,payload),players=players)
            s.STATE.set(self.key,p)

    def finish(self,s,payload):
        with s.STATE.lock:
            p=self.progress(s);context=p.pop('pending',None)
            if not context:return
            reason=str(payload.get('endReason','')).upper()
            if context['mode'] not in ('squad_battles','rivals') or reason not in ('WIN','DRAW','LOSS'):
                s.STATE.set(self.key,p);return
            players=context['players'];starters=[x for x in players if x['index']<11]
            stats=payload.get('items',[])
            stats=[x for x in stats if isinstance(x,dict)] if isinstance(stats,list) else []
            events=[]
            for e in payload.get('events',[]) if isinstance(payload.get('events'),list) else []:
                if not isinstance(e,dict) or not isinstance(e.get('attributes'),list):continue
                attrs=e['attributes'];fields={x.get('key'):x.get('value') for x in attrs if isinstance(x,dict) and x.get('key')!='flag'}
                events.append(dict(name=fields.get('name'),flags=[x.get('value') for x in attrs if isinstance(x,dict) and x.get('key')=='flag'],fields=fields))
            def relevant_events(cards):
                assets={x['assetId'] for x in cards}|{x['resourceId'] for x in cards}
                return [e for e in events if e['fields'].get('player_id') in assets]
            def total(cards,metric):
                ids={x['id'] for x in cards if x['id']>0};matched=[x for x in stats if x.get('id') in ids]
                return sum(mollet_objectives._positive(x.get(metric)) for x in matched) if matched else sum(e['name']=={'goals':'goal','assists':'assist'}[metric] for e in relevant_events(cards))
            if self.event:
                french=[x for x in players if x['nation']==18]
                mexican=[x for x in players if x['leagueId']==341]
                tigres=[x for x in players if x['club']==1970]
                cams=[x for x in players if x['position']=='CAM']
                cam_assists=total(cams,'assists');fr_assists=total(french,'assists')
                changes=[fr_assists,total(mexican,'assists'),total(tigres,'assists'),int(cam_assists>0),
                    int(reason=='WIN' and len(starters)==11 and sum(x['leagueId']==341 for x in starters)>=3 and cam_assists>0),
                    int(reason=='WIN' and len(starters)==11 and any(x['club']==1970 for x in starters) and fr_assists>0)]
            else:
                league=self.spec['league'];cards=[x for x in players if x['leagueId']==league]
                eligible=relevant_events(cards)
                path=s.ROOT/'mollet-event-flags.json';flags=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
                def special(e,kind):
                    explicit={'finesse':('was_finesse','finesse'),'outsideBox':('fromOutsideBox','outsideBox')}[kind]
                    return e['name']=='goal' and (any(e['fields'].get(k) is True or e['fields'].get(k)==1 for k in explicit) or any(f in flags.get(kind,[]) for f in e['flags']))
                changes=[int(reason=='WIN' and len(starters)==11 and all(x['leagueId']==league for x in starters)),
                    total(cards,'goals'),total(cards,'assists'),int(any(special(e,'finesse') for e in eligible)),int(any(special(e,'outsideBox') for e in eligible))]
            p['counts']=[min(row[1],p['counts'][i]+changes[i]) for i,row in enumerate(self.rows)]
            audit=dict(id=context['id'],mode=context['mode'],increments=changes,events=events,at=s.now_s())
            with s.STATE.conn:
                mollet_objectives._put(s,self.key+'_match_'+context['id'],audit);mollet_objectives._put(s,self.key,p)
            s.log.info('PLAYER OBJECTIVES group=%s match=%s increments=%s',self.gid,context['id'],changes)
