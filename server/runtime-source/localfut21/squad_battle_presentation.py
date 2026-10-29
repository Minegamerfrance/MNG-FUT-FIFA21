"""Opponent cosmetics using the native summary kit-data contract."""
import copy,json
TEAMS=(21,22,241,39,243,47)
def theme(s,slot):
 if slot==4:return 243
 if slot==5:return 21 if s.featured_event.bayern_active() else 47
 data=s.squad_battles_weekly.progress(s)
 return TEAMS[(int(slot)+int(data['batch']))%4]
def kits(s,team):
 rows={int(k.get('kitType',-1)):k for k in s.KIT_DB if int(k.get('teamid',0))==team and int(k.get('kitType',-1)) in (0,1)}
 if set(rows)!={0,1}:raise ValueError('Opponent needs both installed kit definitions')
 return rows
def summary(s,data,slot):
 team=theme(s,slot);rows=kits(s,team);data['badgeAssetId']=str(team)
 nested=data.setdefault('sqbt2data',{})
 for typ,key in [(0,'homeKitData'),(1,'awayKitData')]:nested[key]=dict(teamId=team,category=2+typ,year=0)
 return data
def squad(s,data,slot):
 team=theme(s,slot);rows=kits(s,team);actives=[dict(x) for x in data.get('actives',[]) if x.get('itemState') not in ('activeHomeKit','activeAwayKit','activeBadge')]
 for typ,state in [(0,'activeHomeKit'),(1,'activeAwayKit')]:
  row=rows[typ];rid=int(row['resourceId']);actives.append(dict(id=930100000000+slot*10+typ,resourceId=rid,carddbid=rid,assetId=rid,cardassetid=35,itemType='kit',cardsubtypeid=9,itemState=state,owners=1,untradeable=True,category=2+typ,teamid=team,kitType=typ,teamkittypetechid=typ,year=0,resourceGameYear=2021,name=row['name'],rating=83,rareflag=1,value=83))
 badge=s._sb_badges[team]
 rid=int(badge['resourceId'])
 actives.append(dict(id=930100000000+slot*10+8,resourceId=rid,carddbid=rid,assetId=team,cardassetid=39,itemType='custom',cardsubtypeid=11,itemState='activeBadge',teamid=team,owners=1,untradeable=True,rareflag=1,rating=83,value=83))
 data.update(actives=actives,club=[dict(x) for x in actives],badgeAssetId=str(team));summary(s,data,slot);return data
def apply(s):
 if getattr(s,'_opponent_cosmetics_applied',False):return
 s._sb_badges={int(b['assetId']):b for b in json.loads((s.ROOT/'badges.json').read_text(encoding='utf8'))}
 for team in TEAMS:assert team in s._sb_badges;assert set(kits(s,team))=={0,1}
 original_hub=s._native_squad_battle_hub;original_squad=s._native_squad_battle_opponent
 def hub():
  data=original_hub()
  for row in data['sqbtOppSquadList']['sqbtOppSquads']:summary(s,row,int(row['id']))
  return data
 def opponent(slot):return squad(s,original_squad(slot),int(slot))
 s._native_squad_battle_hub=hub;s._native_squad_battle_opponent=opponent
 for module in (s.featured_event,s.featured_totw):
  old_stats=module.stats;old_squad=module.squad;slot=module.ID
  def stats(server,_fn=old_stats,_slot=slot):return summary(server,_fn(server),_slot)
  def detail(server,_fn=old_squad,_slot=slot):return squad(server,_fn(server),_slot)
  module.stats=stats;module.squad=detail
 s._opponent_cosmetics_applied=True

