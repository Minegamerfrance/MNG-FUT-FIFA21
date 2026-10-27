"""Native first-club flow, isolated from all previously saved clubs."""
import json, random, re
from onboarding import Onboarding, OnboardingError, NATIONS, STARTER_POSITIONS

LOAN_MATCHES=10

class BronzeOnboarding(Onboarding):
 def sign_loan(self,offer_id,offers,games):
  item=super().sign_loan(offer_id,offers,1)
  if not item.get('onboardingLoan'):
   item.update(onboardingLoan=True,onboardingLoanRemaining=LOAN_MATCHES,
     loans=1,contract=LOAN_MATCHES,contracts=LOAN_MATCHES)
   with self.state.conn:
    self.state.conn.execute('UPDATE items SET data=? WHERE id=?',(json.dumps(item),item['id']))
  return item

 def create_club(self,payload):
  original=self.cosmetic_templates
  unique={}
  for item in original():unique.setdefault(item['itemState'],item)
  try:
   self.cosmetic_templates=lambda:list(unique.values())
   return super().create_club(payload)
  finally:self.cosmetic_templates=original
 def _starter_resources(self,nation):
  rng=random.Random(str(nation)+str(self.config['display_name']));selected=[]
  for position in STARTER_POSITIONS:
   pool=sorted(rid for rid,m in self.players.items() if rid not in selected
     and rid==int(m.get('assetId',rid)) and m.get('preferredPosition')==position
     and 45<=int(m.get('rating',0))<=64 and int(m.get('rareflag',0))==0
     and m.get('catalogEnabled',True))
   national=[rid for rid in pool if int(self.players[rid].get('nation',0))==nation]
   if national:pool=national
   if not pool:raise OnboardingError(503,'No bronze player for '+position)
   selected.append(rng.choice(pool))
  return selected

def flow(s):
 return BronzeOnboarding(s.STATE,s.PLAYER_DB,s.CFG,lambda:templates(s))

def templates(s):
 result=[];per_kind={};teams=set()
 for meta in s.cosmetics(s):
  kind=meta.get('itemType');kt=meta.get('kitType')
  if kind=='kit' and kt not in (0,1):continue
  if kind!='kit' and meta.get('cardsubtypeid')!=11:continue
  state=('activeHomeKit' if kt==0 else 'activeAwayKit') if kind=='kit' else 'activeBadge'
  if per_kind.get(state,0)>=10:continue
  item=s.cosmetic_item(meta,int(meta['resourceId']),'club')
  item.update(itemState=state,untradeable=True,untradeableCount=1,discardValue=0)
  result.append(item);per_kind[state]=per_kind.get(state,0)+1
 return result

def offers(s):
 result=[]
 for position in s.LOAN_PLAYER_POSITIONS:
  candidates=sorted((rid for rid,m in s.PLAYER_DB.items() if rid==int(m.get('assetId',rid))
    and m.get('preferredPosition')==position and 80<=int(m.get('rating',0))<=86
    and int(m.get('rareflag',0)) in (0,1) and m.get('catalogEnabled',True)),
    key=lambda rid:(-int(s.PLAYER_DB[rid]['rating']),rid))[:s.LOAN_PLAYERS_PER_POSITION]
  for rank,rid in enumerate(candidates,1):
   item=s.STATE.build_player_item(rid,rid,'none',1)
   item.update(contract=LOAN_MATCHES,contracts=LOAN_MATCHES)
   result.append(dict(defId=s.LOAN_OFFER_ID_BASE+len(result),ranking=rank,loans=1,itemData=s._native_player_item(item)))
 return {'loans':result}

def route(s,method,path,query,payload):
 if s.STATE.get('starter_profile_version')!=1:return None
 f=flow(s);root='/ut/game/fifa21/'
 def out(value,status=200):return status,{'Cache-Control':'no-store'},s.json_bytes(value)
 try:
  if path in (root+'user/accountinfo','/ut/v2/game/fifa21/user/accountinfo'):
   result=s.account_info()
   for persona in result['userAccountInfo']['personas']:
    persona['returningUser']=0
    if not f.created():persona['userClubList']=[]
   return out(result)
  if path==root+'user/historical':
   return out(dict(clubName=s.CFG['club_name'],clubAbbr=s.CFG['club_abbr'],isReturningUser=False,returningUserRewards=[]))
  country=re.fullmatch(root+r'user/action/onboarding_country_(\d+)_selected',path)
  if country and method in ('POST','PUT'):
   f.select_country(int(country[1]));return out({})
  if path==root+'user' and method=='POST':
   f.create_club(payload)
   for key in ('club_name','club_abbr'):s.CFG[key]=s.STATE.get(key,s.CFG[key])
   s.STATE._ensure_initial_club_manager()
   return out(dict(bonusPacks=False,login=s.local_user_info(),userData=s._native_user(),
     starterPack=[s._native_player_item(i) if i.get('itemType')=='player' else i for i in f.starter_items()],squad=s._native_squad()))
  if path in (root+'usermassinfo',root+'user/massinfo'):
   if not f.created():return out({'reason':'clubNotCreated'},465)
   doc=s.user_mass_info();doc['loanPlayers']={'loans':[]} if s.onboarding_complete() else offers(s)
   return out(doc)
  if path==root+'loan/players':return out({'loans':[]} if s.onboarding_complete() else offers(s))
  loan=re.fullmatch(root+r'loan/player/(\d+)',path)
  if loan and method in ('POST','PUT'):
   return out(s._native_player_item(f.sign_loan(int(loan[1]),offers(s)['loans'],s.LOAN_GAMES)))
  squad=re.fullmatch(root+r'squad/(\d+)',path)
  if squad and query.get('onboarding',['false'])[0].lower()=='true' and method in ('POST','PUT'):
   f.save_squad(payload,int(squad[1]),True);return out({'id':int(squad[1])})
  if path==root+'onboarding/kits':
   return out(f.cosmetic_choices('kits') if method=='GET' else f.select_kits(payload))
  if path==root+'onboarding/badges' and method=='GET':return out(f.cosmetic_choices('badges'))
  badge=re.fullmatch(root+r'onboarding/badge/(\d+)',path)
  if badge and method=='POST':return out(f.select_badge(int(badge[1])))
 except OnboardingError as e:return out({'reason':str(e)},e.status)
 return None
