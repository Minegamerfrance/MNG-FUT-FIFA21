"""Native featured TOTW opponent for the Squad Battles special tile."""
import copy
ID=4
KEY='featured_totw'
# TOTW 1: 4-1-2-1-2, eleven starters and seven substitutes.
STARTERS=[50546871, 16976162, 50561206, 17009360, 16993483, 16978735, 50553640, 16983733, 50543846, 16798017, 67285444, 50540478, 16978615, 16993570, 16974299, 16982647, 17030220, 17001587]

def roster(s):
    return [rid for rid in STARTERS if rid in s.PLAYER_DB]


def squad(s):
    result=copy.deepcopy(s._native_squad_battle_opponent(3))
    players=[dict(index=i,kitNumber=i+1,itemData=s._native_player_item(s.STATE.build_player_item(rid,941000+i,'none'))) for i,rid in enumerate(roster(s))]
    players += [dict(index=i,kitNumber=0) for i in range(len(players),23)]
    ids=[p['itemData']['id'] for p in players[:11]]
    result.update(id=ID,squadId=ID,squadName='TOTW 1',name='TOTW 1',formation='f41212',players=players,captain=ids[8],chemistry=100,starRating=5,kicktakers=[dict(index=i,id=pid,dream=False) for i,pid in enumerate(ids[6:11])])
    for item in result['actives']:item['id']=int(item['id'])+10000
    result['club']=[dict(item) for item in result['actives']]
    result.setdefault('sqbt2data',{}).update(featuredSquadId=ID)
    return result

def stats(s):
    data=s.squad_battles_results.progress(s);team=squad(s);played=data['played'].get(KEY,{})
    starters=team['players'][:11]
    top=sorted(starters,key=lambda p:-int(p['itemData'].get('rating',0)))[:3]
    return dict(id=ID,squadId=ID,featuredSquadId=ID,clubName='TOTW 1',clubAbbr='TOTW',squadName='TOTW 1',badgeAssetId='1',formation='f41212',rating=round(sum(int(p['itemData'].get('rating',0)) for p in starters)/11),chemistry=100,pointsWon=int(played.get('points',-1)),score=int(played.get('score',-1)),oppScore=int(played.get('oppScore',-1)),endTimeStamp=s.squad_battles_weekly.window(s.now_s())[1],bannerImageName='mng_totw1_v1.dds',difficultyBasedWinPoints=list(s.squad_battles_results.FEATURED_WIN_POINTS),difficultyBasedLossPoints=[0]*7,sqbt2data=dict(stadiumAssetId=s.SQUAD_BATTLE_STADIUM_ID,isHomeTeam=True,topPlayers=[dict(itemData=p['itemData']) for p in top]))

def requested(payload):
    if not isinstance(payload,dict):return False
    for key in ('featuredSquadId','sqbtFeaturedSquadId'):
        value=payload.get(key)
        if not isinstance(value,bool) and str(value)==str(ID):return True
    return payload.get('featureConsumerId')=='sqbttotw'
