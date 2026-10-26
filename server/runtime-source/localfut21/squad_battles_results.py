"""Local MNG Squad Battles settlement with per-match, transactional receipts."""
import copy
import hashlib
import json
import secrets

FEATURED_WIN_POINTS=(1500,1600,1700,1800,1900,2000,2500)
CONTEXT='mng_sb_active_match_v1'
PROGRESS='mng_sb_progress_v1'


def native_result(response):
    """FutDestroyMatchServerResponse, CardsDLL RVA 0x2b1e40.

    Its nested-object/list readers do not accept scalar/null placeholders:
    those shapes can consume the outer stream and wait forever at EOF.
    This pure presentation adapter also repairs old receipts without replaying
    their ledger transaction or overwriting their original saved response.
    """
    result=copy.deepcopy(response)
    if 'squadBattlesScore' in result and not isinstance(result['squadBattlesScore'],dict):
        result['totalSquadBattlesScore']=int(result['squadBattlesScore'])
        points=int(result.get('pointsWon',0))
        result['squadBattlesScore']=dict(finalScore=points,matchResultScore=points,
            skillRatingScore=0,goalsScore=0,matchDifficultyScoreModifier=1.0)
    if not isinstance(result.get('matchCoinPartials'),list):
        result['matchCoinPartials']=[]
    completion=int(result.get('rewardCoins',result.get('completionAward',0)))
    result.update(matchCoins=completion,allCoins=completion,
        participationAward=completion,gameModeAward={'coins':0},
        boostCountLeft=0)
    return result


def _goals(payload, side):
    stats=payload.get(side,{})
    try:
        return max(0,min(999,int(stats['goals'])))
    except (KeyError,TypeError,ValueError):
        return -1


def progress(s):
    return s.squad_battles_weekly.progress(s)


def start(s,slot,payload):
    data=progress(s)
    s.STATE.set(CONTEXT,dict(id=secrets.token_hex(16),slot=int(slot),cycle=data['cycle'],batch=data['batch'],created=s.now_s(),
        difficulty=payload.get('sqbtMatchDifficulty',payload.get('matchDifficulty',0))))


def finish(s,payload):
    if not isinstance(payload,dict):
        return 400,{'reason':'INVALID_MATCH_RESULT'}
    reason=str(payload.get('endReason','')).upper()
    if reason not in ('WIN','DRAW','LOSS','DNF','QUIT','DISCONNECT','FORFEIT'):
        return 400,{'reason':'INVALID_END_REASON'}
    try:
        seconds=max(0,min(86400,int(payload.get('secondsPlayed',0) or 0)))
        difficulty=max(0,min(6,int(payload.get('matchDifficulty',0) or 0)))
    except (ValueError,TypeError):
        return 400,{'reason':'INVALID_MATCH_PARAMETERS'}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    state=s.STATE
    with state.lock:
        context=state.get(CONTEXT)
        if not isinstance(context,dict) or not context.get('id'):
            return 409,{'reason':'SQUAD_BATTLES_MATCH_NOT_STARTED'}
        key='mng_sb_receipt_'+context['id']
        existing=state.get(key)
        if existing:
            response=existing['response']
            objective_payload=existing['payload']
        else:
            data=progress(s)
            won,draw=(reason=='WIN'),(reason=='DRAW')
            lost=not won and not draw
            slot=(str(context.get('batch',0))+':'+str(context['slot'])) if context.get('batch',0) else str(context['slot'])
            featured=context['slot'] in (4,5)
            if featured:slot='featured_totw' if context['slot']==4 else 'featured_event'
            first=slot not in data['played'] and context.get('cycle',data['cycle'])==data['cycle']
            scoring=first and (featured or data['scoringMatches'] < s.squad_battles_weekly.LIMIT)
            difficulty=max(0,min(6,int(payload.get('matchDifficulty',context.get('difficulty',0)) or 0)))
            win_points=FEATURED_WIN_POINTS[difficulty] if featured else (400+100*min(3,max(0,context['slot'])))
            points=win_points if won and scoring else 0
            # Explicit local MNG policy; this is not the official EA coin formula.
            awards={'WIN':1500,'DRAW':1250,'LOSS':1000}
            completion=0 if reason not in awards else max(0,min(50000,int(
                s.CFG.get('squad_battles_'+reason.lower()+'_award',awards[reason]))))
            if first:
                data['played'][slot]=dict(reason=reason,points=points,difficulty=difficulty,score=_goals(payload,'myMatchStats'),oppScore=_goals(payload,'opponentMatchStats'),completedAt=s.now_s())
            data['scoringMatches']+=int(scoring and not featured)
            data['points']+=points
            data['won']+=int(won);data['draw']+=int(draw);data['loss']+=int(lost)
            data['totalMatches']+=1
            credits=state.credits()+completion
            response=dict(endReason=reason,secondsPlayed=seconds,matchDifficulty=difficulty,
                opponentTeamId=context['slot'],items=payload.get('items',[]) if isinstance(payload.get('items'),list) else [],
                matchData=str(payload.get('matchData','') or ''),completionAward=completion,skillAward=0,
                rewardCoins=completion,totalCoins=completion,credits=credits,coins=credits,sessionCoinsBankBalance=credits,
                dnfModifier=1.0,record={k:data[k] for k in ('won','draw','loss')},
                gamesWon=data['won'],gamesDraw=data['draw'],gamesLost=data['loss'],gamesPlayed=data['totalMatches'],
                won=int(won),draw=int(draw),loss=int(lost),squadBattlesScore=data['points'],
                squadBattlePoints=points,pointsWon=points,
                currencies=[dict(name='coins',funds=credits,finalFunds=credits),dict(name='points',funds=0,finalFunds=0)],
                unopenedPacks=dict(preOrderPacks=len(state.unopened_pack_ids()),recoveredPacks=0),
                matchCoinPartials=None,matchCoinMultipliers=[dict(type='DIFFICULTY',value=1.0)],boostConis=0)
            for optional in ('myMatchStats','opponentMatchStats','myRating','opponentRating'):
                if optional in payload:response[optional]=payload[optional]
            response=native_result(response)
            receipt=dict(requestSha256=digest,response=response,payload=payload,createdAt=s.now_s())
            objective_payload=payload
            # One database commit binds credits, progression and receipt.
            state.conn.execute('BEGIN IMMEDIATE')
            try:
                for name,value in [('credits',credits),(PROGRESS,data),(key,receipt)]:
                    state.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                        (name,json.dumps(value)))
                state.conn.commit()
            except Exception:
                state.conn.rollback()
                raise
        # Existing objective handlers consume pending context once; retries can
        # finish any pending group without crediting the match twice.
        s.league_objectives.finish(s,objective_payload)
        s.PENDING_USERSESSION_REFRESH.set()
        s.log.info('SQUAD-BATTLES RESULT match=%s reason=%s replay=%s coins=%s points=%s',
            context['id'],response['endReason'],bool(existing),response['rewardCoins'],response['pointsWon'])
        return 200,native_result(response)
