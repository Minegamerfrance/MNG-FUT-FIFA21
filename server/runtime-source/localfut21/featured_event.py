"""Featured Rulebreakers event team, left Special tile (consumer sqbt)."""
import copy
import event_schedule
ID=5
KEY='featured_event'
ROSTER=[67303268, 67301638, 67309752, 67292771, 67338101, 67325507, 67339006, 67262108, 67320164, 67150100, 67334974, 67321486, 67293296, 67110043, 67296825, 67278280, 67314542, 67349948, 67314266, 67266165, 67299422]
BAYERN_ROSTER=[167495,226851,183907,197445,234396,212622,209658,206113,189596,222492,188545,
               223885,212190,220814,177610,219683,213345,190483,183569,235945,204472,252961,250961]
BAYERN_POSITIONS=('GK','RB','CB','CB','LB','CDM','CDM','RM','CAM','LM','ST')

def bayern_active():return not event_schedule.active('rulebreakers')
def progress_key():return 'featured_bayern' if bayern_active() else KEY

def squad(s):
    result=copy.deepcopy(s._native_squad_battle_opponent(3))
    bayern=bayern_active()
    players=[]
    for i,rid in enumerate(BAYERN_ROSTER if bayern else ROSTER):
        item=s.STATE.build_player_item(rid,952000+i,'none')
        if bayern and i<11:item['preferredPosition']=BAYERN_POSITIONS[i]
        players.append(dict(index=i,kitNumber=i+1,itemData=s._native_player_item(item)))
    # Native squads always contain 23 slot descriptors; unfilled reserves have no itemData.
    players += [dict(index=i,kitNumber=0) for i in range(len(players),23)]
    ids=[p['itemData']['id'] for p in players[:11]]
    result.update(id=ID,squadId=ID,squadName='Rulebreakers 1',name='Rulebreakers 1',formation='f433c',players=players,captain=ids[9],chemistry=100,starRating=5,kicktakers=[dict(index=i,id=pid,dream=False) for i,pid in enumerate(ids[6:11])])
    if bayern:result.update(squadName='Bayern Munich',name='Bayern Munich',formation='f4231a',captain=ids[0])
    for item in result['actives']:item['id']=int(item['id'])+20000
    result['club']=[dict(item) for item in result['actives']]
    result['manager']=[s._native_manager_item(s.STATE.build_manager_item(1169894,953999,'none'),in_squad=True)]
    result.setdefault('sqbt2data',{}).update(featuredSquadId=ID)
    return result

def stats(s):
    data=s.squad_battles_results.progress(s);team=squad(s);played=data['played'].get(progress_key(),{})
    starters=team['players'][:11];top=sorted(starters,key=lambda p:-int(p['itemData'].get('rating',0)))[:3]
    bayern=bayern_active();name='Bayern Munich' if bayern else 'Rulebreakers 1'
    return dict(id=ID,squadId=ID,featuredSquadId=ID,clubName=name,clubAbbr='FCB' if bayern else 'RB1',squadName=name,badgeAssetId='21' if bayern else '1',formation=team['formation'],rating=round(sum(int(p['itemData'].get('rating',0)) for p in starters)/11),chemistry=100,pointsWon=int(played.get('points',-1)),score=int(played.get('score',-1)),oppScore=int(played.get('oppScore',-1)),endTimeStamp=s.squad_battles_weekly.window(s.now_s())[1],bannerImageName='' if bayern else 'mng_rulebreakers1_v1.dds',difficultyBasedWinPoints=list(s.squad_battles_results.FEATURED_WIN_POINTS),difficultyBasedLossPoints=[0]*7,sqbt2data=dict(stadiumAssetId=s.SQUAD_BATTLE_STADIUM_ID,isHomeTeam=True,topPlayers=[dict(itemData=p['itemData']) for p in top]))

def requested(payload):
    if not isinstance(payload,dict):return False
    for key in ('featuredSquadId','sqbtFeaturedSquadId'):
        value=payload.get(key)
        if not isinstance(value,bool) and str(value)==str(ID):return True
    return payload.get('featureConsumerId')=='sqbt' and 'sqbtOpponentSquadId' not in payload
