"""Featured Rulebreakers event team, left Special tile (consumer sqbt)."""
import copy
ID=5
KEY='featured_event'
ROSTER=[67303268, 67301638, 67309752, 67292771, 67338101, 67325507, 67339006, 67262108, 67320164, 67150100, 67334974, 67321486, 67293296, 67110043, 67296825, 67278280, 67314542, 67349948, 67314266, 67299422]

def squad(s):
    result=copy.deepcopy(s._native_squad_battle_opponent(3))
    players=[dict(index=i,kitNumber=i+1,itemData=s._native_player_item(s.STATE.build_player_item(rid,952000+i,'none'))) for i,rid in enumerate(ROSTER)]
    # Native squads always contain 23 slot descriptors; unfilled reserves have no itemData.
    players += [dict(index=i,kitNumber=0) for i in range(len(players),23)]
    ids=[p['itemData']['id'] for p in players[:11]]
    result.update(id=ID,squadId=ID,squadName='Rulebreakers 1',name='Rulebreakers 1',formation='f433c',players=players,captain=ids[9],chemistry=100,starRating=5,kicktakers=[dict(index=i,id=pid,dream=False) for i,pid in enumerate(ids[6:11])])
    for item in result['actives']:item['id']=int(item['id'])+20000
    result['club']=[dict(item) for item in result['actives']]
    result['manager']=[s._native_manager_item(s.STATE.build_manager_item(1169894,953999,'none'),in_squad=True)]
    result.setdefault('sqbt2data',{}).update(featuredSquadId=ID)
    return result

def stats(s):
    data=s.squad_battles_results.progress(s);team=squad(s);played=data['played'].get(KEY,{})
    starters=team['players'][:11];top=sorted(starters,key=lambda p:-int(p['itemData'].get('rating',0)))[:3]
    return dict(id=ID,squadId=ID,featuredSquadId=ID,clubName='Rulebreakers 1',clubAbbr='RB1',squadName='Rulebreakers 1',badgeAssetId='1',formation='f433c',rating=round(sum(int(p['itemData'].get('rating',0)) for p in starters)/11),chemistry=100,pointsWon=int(played.get('points',-1)),score=int(played.get('score',-1)),oppScore=int(played.get('oppScore',-1)),endTimeStamp=s.squad_battles_weekly.window(s.now_s())[1],bannerImageName='mng_rulebreakers1_v1.dds',difficultyBasedWinPoints=list(s.squad_battles_results.FEATURED_WIN_POINTS),difficultyBasedLossPoints=[0]*7,sqbt2data=dict(stadiumAssetId=s.SQUAD_BATTLE_STADIUM_ID,isHomeTeam=True,topPlayers=[dict(itemData=p['itemData']) for p in top]))

def requested(payload):
    if not isinstance(payload,dict):return False
    for key in ('featuredSquadId','sqbtFeaturedSquadId'):
        value=payload.get(key)
        if not isinstance(value,bool) and str(value)==str(ID):return True
    return payload.get('featureConsumerId')=='sqbt' and 'sqbtOpponentSquadId' not in payload
