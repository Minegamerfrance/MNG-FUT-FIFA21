"""Rulebreakers Halloween objectives and transactional mixed rewards."""
import json
import uuid
import mollet_objectives as mo
from player_objectives import Campaign

DUBOIS=67325507
ROWS=(
 ('Une nuit sur le terrain',1,0,'Disputez un match en Rivals ou en Clashs d’équipes.'),
 ('Les débuts de Dubois',5,525,'Disputez 5 matchs avec Léo Dubois Rulebreakers en Rivals ou en Clashs d’équipes.'),
 ('Dubois victorieux',3,520,'Remportez 3 matchs avec Léo Dubois Rulebreakers en Rivals ou en Clashs d’équipes.'),
 ('Présences effrayantes',10,0,'Disputez 10 matchs avec un joueur Rulebreakers en Rivals ou en Clashs d’équipes.'),
 ('Victoires terrifiantes',10,0,'Remportez 10 matchs avec un joueur Rulebreakers en Rivals ou en Clashs d’équipes.'),
 ('Des passes à faire peur',10,0,'Adressez 10 passes décisives avec des joueurs Rulebreakers en Rivals ou en Clashs d’équipes.'),
 ('Des buts effrayants',10,0,'Marquez 10 buts avec des joueurs Rulebreakers en Rivals ou en Clashs d’équipes.'),
)
COSMETICS={
 4:dict(resourceId=8120201,assetId=201,cardassetid=37,itemType='ball',cardsubtypeid=30,
        family='balls',table='fcc_balls',ballid=201,category=1,name='Ballon Citrouille'),
 5:dict(resourceId=6311198,assetId=6311198,cardassetid=35,itemType='kit',cardsubtypeid=9,
        family='kits',table='fcc_kitcards',teamid=114847,kitType=0,teamkittypetechid=0,category=2,name='Maillot Rulebreakers'),
 6:dict(resourceId=6310854,assetId=6310854,cardassetid=35,itemType='kit',cardsubtypeid=9,
        family='kits',table='fcc_kitcards',teamid=114840,kitType=0,teamkittypetechid=0,category=2,name='Maillot Chat effrayant'),
}

class Nights(Campaign):
 def __init__(self):
  super().__init__(7102,dict(key='rulebreakers_scary_nights_v1',title='Nuits effrayantes',
   subTitle='Échappez à cette nuit terrifiante et remportez plusieurs récompenses.',
   leagueName='Rulebreakers',priority=2,displayOrder=list(range(7))),ROWS,xp=0,group_xp=150,event=True)

 def amount(self,index):return 150 if index is None else {3:100,5:25,6:25}.get(index,0)

 def item(self,s,index,identifier=0):
  if index==0:
   item=s.STATE.build_player_item(DUBOIS,identifier,'unassigned',loan_games=10)
   item.update(scaryNightsLoan=True,scaryNightsLoanRemaining=10,loans=1,contract=10,contracts=10)
  else:
   item=dict(COSMETICS[index],id=identifier,carddbid=COSMETICS[index]['resourceId'],
    timestamp=s.now_s(),itemState='free',pile='unassigned',owners=1,stackCount=1,
    rating=90,value=90,rareflag=1,islocked=0,resourceGameYear=2021,discardValue=0,lastSalePrice=0)
  item.update(untradeable=True,untradeableCount=1,objectiveReward=True)
  return item

 def awards(self,s,index=None):
  awards=[]
  if index is None or index in (1,2):
   a=s._pack_award(523 if index is None else self.rows[index][2]);a['halId']=a['assetId'];awards.append(a)
  elif index in (0,4,5,6):
   item=s._native_pack_item(self.item(s,index));rid=item['resourceId']
   awards.append(dict(type='item',awardType='item',halId=0,assetId=rid,value=rid,awardValue=rid,
    count=1,awardCount=1,isItem=True,isPack=False,untradeable=True,isUntradeable=True,
    name='Léo Dubois Rulebreakers — prêt de 10 matchs' if index==0 else item['name'],
    items='Léo Dubois' if index==0 else item['name'],itemsAmount=1,
    loans=1 if index==0 else 0,itemData=item))
  if self.amount(index):awards.append(self.xp_award(self.amount(index)))
  return awards

 def group(self,s,details=True):
  g=super().group(s,details)
  for i,o in enumerate(g.get('objectives',[])):o.update(xp=self.amount(i),xpReward=self.amount(i))
  return g

 def claim(self,s,index=None):
  with s.STATE.lock:
   p=self.progress(s)
   taken=p.get('claimed') if index is None else index in p.get('claimedObjectives',[])
   if taken:return 200,dict(alreadyClaimed=True,awards=[],awardsList=[],itemList=[],grantedItems=[],xpAward=0)
   complete=all(p['counts'][i]>=r[1] for i,r in enumerate(self.rows)) if index is None else p['counts'][index]>=self.rows[index][1]
   if not complete:return 403,dict(reason='OBJECTIVES_INCOMPLETE',awards=[],itemList=[])
   xp=int(s.STATE.get('scmp_user_xp',0) or 0)+self.amount(index);items=[]
   if index in (0,4,5,6):
    iid=max(int(s.STATE.get('next_item_id',900000000000))+1,int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM items').fetchone()[0]))
    items=[self.item(s,index,iid)]
   if index is None:p['claimed']=True
   else:p['claimedObjectives']=sorted(set(p.get('claimedObjectives',[]))|{index})
   with s.STATE.conn:
    for item in items:
     s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',(item['id'],item['resourceId'],'unassigned',json.dumps(item)))
     mo._put(s,'next_item_id',item['id'])
    if index is None or index in (1,2):
     pid=523 if index is None else self.rows[index][2]
     s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',(pid,json.dumps(dict(source='scary_nights_objective',objectiveId=self.gid*100+(index+1 if index is not None else 0),created=s.now_s(),untradeable=True))))
    mo._put(s,'scmp_user_xp',xp);mo._put(s,self.key,p)
   native=[s._native_pack_item(x) for x in items];a=self.awards(s,index)
   s.PENDING_USERSESSION_REFRESH.set()
   return 200,dict(alreadyClaimed=False,awards=a,awardsList=a,itemList=native,grantedItems=native,xpAward=self.amount(index),userXp=xp)

 def start(self,s,payload,response):
  with s.STATE.lock:
   p=self.progress(s)
   if p.get('pending'):return
   players=[]
   for slot in response.get('squad',{}).get('players',[]):
    item=slot.get('itemData') or {};iid=int(item.get('id',0));owned=s.STATE.get_item(iid)
    if not owned or owned.get('dream') or owned.get('concept'):continue
    rid=int(owned.get('resourceId',0));card=s.PLAYER_DB.get(rid,{})
    players.append(dict(id=iid,resourceId=rid,assetId=int(card.get('assetId',rid)),
     rareflag=int(card.get('rareflag',owned.get('rareflag',0))),index=int(slot.get('index',99))))
   p['pending']=dict(id=uuid.uuid4().hex,mode=mo.mode(s,payload),players=players)
   s.STATE.set(self.key,p)

 def finish(self,s,payload):
  with s.STATE.lock:
   p=self.progress(s);ctx=p.pop('pending',None)
   if not ctx:return
   reason=str(payload.get('endReason','')).upper()
   if reason not in ('WIN','DRAW','LOSS'):s.STATE.set(self.key,p);return
   raw=payload.get('items',[]);stats={int(x.get('id',0)):x for x in raw if isinstance(x,dict)} if isinstance(raw,list) else {}
   # Starters participate; bench players count only when match stats show participation.
   players=[x for x in ctx['players'] if x['index']<11 or any(mo._positive(stats.get(x['id'],{}).get(k)) for k in ('minutesPlayed','minutes','goals','assists'))]
   rl=[x for x in players if x['rareflag']==22];dubois=any(x['resourceId']==DUBOIS for x in players)
   def total(metric):
    ids={x['id'] for x in rl};matched=[stats[i] for i in ids if i in stats]
    if matched:return sum(mo._positive(x.get(metric)) for x in matched)
    assets={x['assetId'] for x in rl}|{x['resourceId'] for x in rl};n=0
    for e in payload.get('events',[]) if isinstance(payload.get('events'),list) else []:
     if not isinstance(e,dict):continue
     attrs={a.get('key'):a.get('value') for a in e.get('attributes',[]) if isinstance(a,dict)}
     if attrs.get('name')=={'goals':'goal','assists':'assist'}[metric] and str(attrs.get('player_id')) in {str(a) for a in assets}:n+=1
    return n
   changes=[0]*7
   if ctx['mode'] in ('squad_battles','rivals') and not p.get('claimed'):
    changes=[1,int(dubois),int(dubois and reason=='WIN'),int(bool(rl)),int(bool(rl) and reason=='WIN'),total('assists'),total('goals')]
    p['counts']=[min(row[1],p['counts'][i]+changes[i]) for i,row in enumerate(self.rows)]
   with s.STATE.conn:
    # This reward's loan duration is consumed once per completed appearance.
    for x in players:
     item=s.STATE.get_item(x['id'])
     if not item or not item.get('scaryNightsLoan') or int(item.get('loans',0))<=0:continue
     remaining=int(item.get('scaryNightsLoanRemaining',item.get('contracts',0)) or 0)
     if 'scaryNightsLoanRemaining' not in item and int(item.get('loans',0))>1:remaining=int(item['loans'])
     remaining=max(0,remaining-1)
     item.update(scaryNightsLoanRemaining=remaining,contract=remaining,contracts=remaining,loans=1 if remaining else 0)
     if remaining==0:
      item.update(loanExpired=True,pile='expired_loan')
      for row in s.STATE.conn.execute('SELECT id,data FROM squads').fetchall():
       squad=json.loads(row['data']);old=squad.get('players',[])
       squad['players']=[slot for slot in old if slot.get('itemId',slot.get('itemData',{}).get('id',slot.get('id',0)))!=item['id']]
       if len(old)!=len(squad['players']):s.STATE.conn.execute('UPDATE squads SET data=? WHERE id=?',(json.dumps(squad),row['id']))
     s.STATE.conn.execute('UPDATE items SET pile=?,data=? WHERE id=?',(item.get('pile','club'),json.dumps(item),item['id']))
    mo._put(s,self.key+'_match_'+ctx['id'],dict(increments=changes,mode=ctx['mode'],at=s.now_s()))
    mo._put(s,self.key,p)

