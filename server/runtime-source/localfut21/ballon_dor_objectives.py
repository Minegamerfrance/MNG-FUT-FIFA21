"""Ballon d'Or 2026: persistent six-objective career and fifteen-appearance loan."""
import json,uuid
import mollet_objectives as mo
from player_objectives import Campaign
PLAYER=67310990
ROWS=(
 ('Les débuts aux Spurs',6,301,'Disputez 6 matchs avec Harry Kane, quelle que soit sa version, en Rivals ou en Clashs d’équipes.'),
 ('Les Trois Lions',14,303,'Disputez 14 matchs avec au moins un joueur anglais titulaire en Rivals ou en Clashs d’équipes.'),
 ('Un véritable numéro neuf',65,404,'Disputez 65 matchs avec au moins un joueur au poste BU titulaire en Rivals ou en Clashs d’équipes.'),
 ('Le départ pour Munich',42,403,'Remportez 42 matchs avec au moins un joueur du Bayern Munich titulaire en Rivals ou en Clashs d’équipes.'),
 ('Le sens du collectif',8,521,'Adressez 8 passes décisives en Rivals ou en Clashs d’équipes, comme Harry Kane avec le Bayern et l’Angleterre en 2025-2026.'),
 ('Le Soulier d’or',73,405,'Marquez 73 buts en Rivals ou en Clashs d’équipes, comme Harry Kane avec le Bayern et l’Angleterre en 2025-2026.'),
)
class BallonDor(Campaign):
 def __init__(self):
  super().__init__(7201,dict(player=PLAYER,key='mng_ballon_or_2026_v1',title='La route du Ballon d’or 2026',
   subTitle='Revivez le parcours de Harry Kane, des Spurs à Munich, et obtenez sa version Ballon d’or 2026 en prêt pour 15 matchs !',
   leagueName='MNG FUT',priority=1,displayOrder=list(range(6))),ROWS,xp=0,group_xp=1000)
 def progress(self,s):
  p=super().progress(s)
  if p.get('criteriaVersion')!=2:
   p['counts'][:2]=[0,0]
   p['claimedObjectives']=[i for i in p.get('claimedObjectives',[]) if i not in (0,1)]
   p['criteriaVersion']=2
   s.STATE.set(self.key,p)
  return p
 def item(self,s,identifier=0):
  item=s.STATE.build_player_item(self.spec['player'],identifier,'unassigned',loan_games=1)
  item.update(ballonDorLoan=True,ballonDorLoanRemaining=15,ballonDorLoanTotal=15,loans=1,contract=15,contracts=15,
    untradeable=True,untradeableCount=1,objectiveReward=True)
  return item
 def awards(self,s,index=None):
  if index is not None:
   reward=s._pack_award(self.rows[index][2]);reward['halId']=reward['assetId']
   return [reward]
  item=s._native_pack_item(self.item(s))
  # Objective reward previews use loans as the visible match count; the owned
  # instance keeps loans=1 and contracts=remaining for actual match handling.
  item['loans']=15
  name=self.spec.get('rewardName','Harry Kane Ballon d’or 2026 — prêt de 15 matchs')
  return [dict(type='item',awardType='item',halId=0,assetId=PLAYER,value=PLAYER,awardValue=PLAYER,count=1,awardCount=1,
   isItem=True,isPack=False,untradeable=True,isUntradeable=True,name=name,items=name,itemsAmount=1,itemData=item),self.xp_award(self.group_xp)]
 def claim(self,s,index=None):
  with s.STATE.lock:
   if not self.unlocked(s):return 403,dict(reason='PREREQUISITE_INCOMPLETE',requiredGroupId=7201,awards=[],itemList=[])
   p=self.progress(s)
   if p.get('claimed') if index is None else index in p.get('claimedObjectives',[]):
    return 200,dict(alreadyClaimed=True,awards=[],awardsList=[],itemList=[],grantedItems=[],xpAward=0)
   needed=range(6) if index is None else [index]
   if any(p['counts'][i]<self.rows[i][1] for i in needed):return 403,dict(reason='OBJECTIVES_INCOMPLETE',awards=[],itemList=[])
   items=[]
   amount=self.group_xp if index is None else 0
   xp=int(s.STATE.get('scmp_user_xp',0) or 0)+amount
   if index is None:
    iid=max(int(s.STATE.get('next_item_id',900000000000))+1,int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM items').fetchone()[0]))
    items=[self.item(s,iid)];p['claimed']=True
   else:p['claimedObjectives']=sorted(set(p.get('claimedObjectives',[]))|{index})
   with s.STATE.conn:
    for item in items:
     s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',(item['id'],self.spec['player'],'unassigned',json.dumps(item)))
     mo._put(s,'next_item_id',item['id'])
    if index is not None:
     s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',(self.rows[index][2],json.dumps(dict(source='ballon_dor_objective',objectiveId=self.gid*100+index+1,created=s.now_s(),untradeable=True))))
    mo._put(s,'scmp_user_xp',xp)
    mo._put(s,self.key,p)
   native=[s._native_pack_item(i) for i in items];a=self.awards(s,index);s.PENDING_USERSESSION_REFRESH.set()
   return 200,dict(alreadyClaimed=False,awards=a,awardsList=a,itemList=native,grantedItems=native,xpAward=amount,userXp=xp)
 def start(self,s,payload,response):
  with s.STATE.lock:
   if not self.unlocked(s):return
   p=self.progress(s)
   if p.get('pending'):return
   players=[]
   for slot in response.get('squad',{}).get('players',[]):
    preview=slot.get('itemData') or {};item=s.STATE.get_item(int(preview.get('id',0)))
    if not item or item.get('dream') or item.get('concept'):continue
    card=s.PLAYER_DB.get(int(item.get('resourceId',0)))
    if card:players.append(dict(id=item['id'],resourceId=item['resourceId'],assetId=int(card['assetId']),
      club=int(card.get('teamid',0)),leagueId=int(card.get('leagueId',0)),nation=int(card.get('nation',0)),position=str(item.get('preferredPosition',card.get('preferredPosition',''))),index=int(slot.get('index',99))))
   p['pending']=dict(id=uuid.uuid4().hex,mode=mo.mode(s,payload),players=players);s.STATE.set(self.key,p)
 def finish(self,s,payload):
  with s.STATE.lock:
   p=self.progress(s);ctx=p.pop('pending',None)
   if not ctx:return
   reason=str(payload.get('endReason','')).upper()
   if reason not in ('WIN','DRAW','LOSS'):s.STATE.set(self.key,p);return
   raw=payload.get('items',[]);stats={int(x.get('id',0)):x for x in raw if isinstance(x,dict)} if isinstance(raw,list) else {}
   participants=[x for x in ctx['players'] if x['index']<11 or any(mo._positive(stats.get(x['id'],{}).get(k)) for k in ('minutesPlayed','minutes','goals','assists'))]
   starters=[x for x in ctx['players'] if x['index']<11]
   def total(cards,metric):
    matched=[stats[x['id']] for x in cards if x['id'] in stats]
    if any(metric in row for row in matched):return sum(mo._positive(x.get(metric)) for x in matched)
    ids={str(x[k]) for x in cards for k in ('id','assetId','resourceId')};n=0
    for e in payload.get('events',[]) if isinstance(payload.get('events'),list) else []:
     if not isinstance(e,dict):continue
     attrs={a.get('key'):a.get('value') for a in e.get('attributes',[]) if isinstance(a,dict)}
     if attrs.get('name')=={'goals':'goal','assists':'assist'}[metric] and str(attrs.get('player_id')) in ids:n+=1
    return n
   changes=[0]*6
   if ctx['mode'] in ('squad_battles','rivals') and not p.get('claimed') and self.unlocked(s):
    changes=self.increments(participants,starters,total,reason)
    p['counts']=[min(row[1],p['counts'][i]+changes[i]) for i,row in enumerate(self.rows)]
   with s.STATE.conn:
    for x in participants:
     item=s.STATE.get_item(x['id'])
     if not item or not item.get('ballonDorLoan') or not int(item.get('loans',0)):continue
     remaining=max(0,int(item['ballonDorLoanRemaining'])-1);item.update(ballonDorLoanRemaining=remaining,contract=remaining,contracts=remaining,loans=1 if remaining else 0)
     if not remaining:
      item.update(loanExpired=True,pile='expired_loan')
      for row in s.STATE.conn.execute('SELECT id,data FROM squads').fetchall():
       squad=json.loads(row['data']);old=squad.get('players',[])
       squad['players']=[slot for slot in old if slot.get('itemId',slot.get('itemData',{}).get('id',slot.get('id',0)))!=item['id']]
       if len(old)!=len(squad['players']):s.STATE.conn.execute('UPDATE squads SET data=? WHERE id=?',(json.dumps(squad),row['id']))
     s.STATE.conn.execute('UPDATE items SET pile=?,data=? WHERE id=?',(item.get('pile','club'),json.dumps(item),item['id']))
    mo._put(s,self.key+'_match_'+ctx['id'],dict(increments=changes,mode=ctx['mode'],at=s.now_s()));mo._put(s,self.key,p)

 def unlocked(self,s):return True
 def increments(self,participants,starters,total,reason):
  return [int(any(x['assetId']==202126 for x in participants)),int(any(x['nation']==14 for x in starters)),
   int(any(x['position']=='ST' for x in starters)),int(reason=='WIN' and any(x['club']==21 for x in starters)),total(participants,'assists'),total(participants,'goals')]
 def group(self,s,details=True):
  result=super().group(s,details)
  result['groupIdsToUnlock']=[7202]
  return result

DEMBELE=67340307
DEMBELE_ROWS=(
 ('Le prodige de Rennes',6,301,'Disputez 6 matchs avec Ousmane Dembélé, quelle que soit sa version, en Rivals ou en Clashs d’équipes.'),
 ('Le roi des nuits européennes',8,303,'Marquez 8 buts avec des joueurs français en Rivals ou en Clashs d’équipes.'),
 ('Le maître de la Ligue 1',21,403,'Marquez 21 buts avec des joueurs de Ligue 1 titulaires en Rivals ou en Clashs d’équipes.'),
 ('Le génie du collectif',16,521,'Adressez 16 passes décisives en Rivals ou en Clashs d’équipes.'),
 ('Paris au sommet de l’Europe',53,404,'Disputez 53 matchs avec au moins un joueur du Paris Saint-Germain titulaire en Rivals ou en Clashs d’équipes.'),
 ('Une saison en or',35,405,'Marquez 35 buts avec des joueurs français en Rivals ou en Clashs d’équipes.'),
)
class DembeleBallonDor(BallonDor):
 def __init__(self):
  Campaign.__init__(self,7202,dict(player=DEMBELE,key='mng_ballon_or_2025_v1',title='La route du Ballon d’or 2025',
   subTitle='Revivez le parcours d’Ousmane Dembélé et obtenez sa version Ballon d’or 2025 en prêt pour 15 matchs !',
   rewardName='Ousmane Dembélé Ballon d’or 2025 — prêt de 15 matchs',leagueName='MNG FUT',priority=2,displayOrder=list(range(6))),DEMBELE_ROWS,xp=0,group_xp=1000)
 def progress(self,s):return Campaign.progress(self,s)
 def unlocked(self,s):return bool((s.STATE.get('mng_ballon_or_2026_v1',{}) or {}).get('claimed'))
 def group(self,s,details=True):
  result=Campaign.group(self,s,details)
  result.update(requiredGroupIds=[7201],isLocked=not self.unlocked(s),locked=not self.unlocked(s))
  if not self.unlocked(s):
   result.update(groupState=0,state=0,subTitle='Verrouillé : terminez La route du Ballon d’or 2026 et récupérez Kane pour débloquer ces défis.')
   for objective in result.get('objectives',[]):objective['state']='LOCKED'
  return result
 def increments(self,participants,starters,total,reason):
  french=[x for x in participants if x['nation']==18]
  ligue1=[x for x in starters if x['leagueId']==16]
  goals=total(french,'goals')
  return [int(any(x['assetId']==231443 for x in participants)),goals,total(ligue1,'goals'),total(participants,'assists'),int(any(x['club']==73 for x in starters)),goals]
