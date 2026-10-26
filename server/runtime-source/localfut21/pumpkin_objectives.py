"""Pumpkin-kit objectives gated by the exact starting Gignac Rulebreakers."""
import json
import uuid
import mollet_objectives as mo
from player_objectives import Campaign
GIGNAC=67262108
PAULINHO=67296825
KIT=dict(resourceId=6313291,assetId=6313291,cardassetid=35,itemType='kit',cardsubtypeid=9,
 family='kits',table='fcc_kitcards',teamid=113291,kitType=0,teamkittypetechid=0,category=2,name='Maillot Citrouille')
ROWS=(
 ('La citrouille entre en jeu',5,0,'Disputez 5 matchs en Rivals ou en Clashs d’équipes avec Gignac Rulebreakers titulaire.'),
 ('Une récolte victorieuse',3,525,'Remportez 3 matchs en Rivals ou en Clashs d’équipes avec Gignac Rulebreakers titulaire.'),
 ('Des passes ensorcelées',10,525,'Adressez 10 passes décisives en Rivals ou en Clashs d’équipes avec Gignac Rulebreakers titulaire.'),
 ('Des buts à glacer le sang',10,525,'Marquez 10 buts en Rivals ou en Clashs d’équipes avec Gignac Rulebreakers titulaire.'),
)
class Pumpkins(Campaign):
 def __init__(self):
  super().__init__(8003,dict(key='pumpkin_harvest_v1',title='La récolte des citrouilles',
   subTitle='Bravez cette récolte terrifiante avec Gignac Rulebreakers et remportez le maillot Citrouille !',
   leagueName='Rulebreakers',priority=0,displayOrder=list(range(4))),ROWS,xp=25,group_xp=250,event=True)
 def item(self,s,index,identifier=0):
  if index==0:
   item=s.STATE.build_player_item(PAULINHO,identifier,'unassigned',loan_games=10)
   item.update(pumpkinLoan=True,pumpkinLoanRemaining=10,loans=1,contract=10,contracts=10)
  else:
   item=dict(KIT,id=identifier,carddbid=KIT['resourceId'],timestamp=s.now_s(),itemState='free',pile='unassigned',
    owners=1,stackCount=1,rating=90,value=90,rareflag=1,islocked=0,resourceGameYear=2021,discardValue=0,lastSalePrice=0)
  item.update(untradeable=True,untradeableCount=1,objectiveReward=True)
  return item
 def awards(self,s,index=None):
  if index in (1,2,3):
   a=s._pack_award(525);a['halId']=a['assetId']
  else:
   item=s._native_pack_item(self.item(s,index));rid=item['resourceId'];name='Paulinho Rulebreakers — prêt de 10 matchs' if index==0 else KIT['name']
   a=dict(type='item',awardType='item',halId=0,assetId=rid,value=rid,awardValue=rid,count=1,awardCount=1,
    isItem=True,isPack=False,untradeable=True,isUntradeable=True,name=name,items=name,itemsAmount=1,itemData=item)
  return [a,self.xp_award(250 if index is None else 25)]
 def claim(self,s,index=None):
  with s.STATE.lock:
   p=self.progress(s)
   if p.get('claimed') if index is None else index in p.get('claimedObjectives',[]):
    return 200,dict(alreadyClaimed=True,awards=[],awardsList=[],itemList=[],grantedItems=[],xpAward=0)
   needed=range(4) if index is None else [index]
   if any(p['counts'][i]<self.rows[i][1] for i in needed):return 403,dict(reason='OBJECTIVES_INCOMPLETE',awards=[],itemList=[])
   xp=int(s.STATE.get('scmp_user_xp',0) or 0)+(250 if index is None else 25);items=[]
   if index in (None,0):
    iid=max(int(s.STATE.get('next_item_id',900000000000))+1,int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM items').fetchone()[0]))
    items=[self.item(s,index,iid)]
   if index is None:p['claimed']=True
   else:p['claimedObjectives']=sorted(set(p.get('claimedObjectives',[]))|{index})
   with s.STATE.conn:
    for item in items:
     s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',(item['id'],item['resourceId'],'unassigned',json.dumps(item)))
     mo._put(s,'next_item_id',item['id'])
    if index in (1,2,3):s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',(525,json.dumps(dict(source='pumpkin_objective',objectiveId=self.gid*100+index+1,created=s.now_s(),untradeable=True))))
    mo._put(s,'scmp_user_xp',xp);mo._put(s,self.key,p)
   native=[s._native_pack_item(x) for x in items];a=self.awards(s,index);s.PENDING_USERSESSION_REFRESH.set()
   return 200,dict(alreadyClaimed=False,awards=a,awardsList=a,itemList=native,grantedItems=native,xpAward=250 if index is None else 25,userXp=xp)
 def start(self,s,payload,response):
  with s.STATE.lock:
   p=self.progress(s)
   if p.get('pending'):return
   players=[]
   for slot in response.get('squad',{}).get('players',[]):
    preview=slot.get('itemData') or {};item=s.STATE.get_item(int(preview.get('id',0)))
    if not item or item.get('dream') or item.get('concept'):continue
    rid=int(item.get('resourceId',0));card=s.PLAYER_DB.get(rid)
    if card:players.append(dict(id=item['id'],resourceId=rid,assetId=int(card['assetId']),index=int(slot.get('index',99))))
   p['pending']=dict(id=uuid.uuid4().hex,mode=mo.mode(s,payload),players=players);s.STATE.set(self.key,p)
 def finish(self,s,payload):
  with s.STATE.lock:
   p=self.progress(s);ctx=p.pop('pending',None)
   if not ctx:return
   reason=str(payload.get('endReason','')).upper()
   if reason not in ('WIN','DRAW','LOSS'):s.STATE.set(self.key,p);return
   raw=payload.get('items',[]);stats={int(x.get('id',0)):x for x in raw if isinstance(x,dict)} if isinstance(raw,list) else {}
   players=[x for x in ctx['players'] if x['index']<11 or any(mo._positive(stats.get(x['id'],{}).get(k)) for k in ('minutesPlayed','minutes','goals','assists'))]
   def total(metric):
    matched=[stats[x['id']] for x in players if x['id'] in stats]
    if any(metric in row for row in matched):return sum(mo._positive(x.get(metric)) for x in matched)
    assets={str(x[k]) for x in players for k in ('assetId','resourceId')};n=0
    for e in payload.get('events',[]) if isinstance(payload.get('events'),list) else []:
     if not isinstance(e,dict):continue
     attrs={a.get('key'):a.get('value') for a in e.get('attributes',[]) if isinstance(a,dict)}
     if attrs.get('name')=={'goals':'goal','assists':'assist'}[metric] and str(attrs.get('player_id')) in assets:n+=1
    return n
   gate=any(x['resourceId']==GIGNAC and x['index']<11 for x in ctx['players'])
   changes=[1,int(reason=='WIN'),total('assists'),total('goals')] if gate and ctx['mode'] in ('squad_battles','rivals') and not p.get('claimed') else [0]*4
   p['counts']=[min(row[1],p['counts'][i]+changes[i]) for i,row in enumerate(self.rows)]
   with s.STATE.conn:
    for x in players:
     item=s.STATE.get_item(x['id'])
     if not item or not item.get('pumpkinLoan') or int(item.get('loans',0))<=0:continue
     remaining=max(0,int(item['pumpkinLoanRemaining'])-1);item.update(pumpkinLoanRemaining=remaining,contract=remaining,contracts=remaining,loans=1 if remaining else 0)
     if not remaining:
      item.update(loanExpired=True,pile='expired_loan')
      for row in s.STATE.conn.execute('SELECT id,data FROM squads').fetchall():
       squad=json.loads(row['data']);old=squad.get('players',[]);squad['players']=[slot for slot in old if slot.get('itemId',slot.get('itemData',{}).get('id',slot.get('id',0)))!=item['id']]
       if len(old)!=len(squad['players']):s.STATE.conn.execute('UPDATE squads SET data=? WHERE id=?',(json.dumps(squad),row['id']))
     s.STATE.conn.execute('UPDATE items SET pile=?,data=? WHERE id=?',(item.get('pile','club'),json.dumps(item),item['id']))
    mo._put(s,self.key+'_match_'+ctx['id'],dict(increments=changes,mode=ctx['mode'],at=s.now_s()));mo._put(s,self.key,p)
