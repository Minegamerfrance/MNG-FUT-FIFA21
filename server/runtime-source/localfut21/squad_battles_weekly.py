"""Twenty scoring matches; Sunday 10:00 metropolitan France rollover.

Uses the EU last-Sunday DST rule (1996 onward), without a tzdata dependency
on Windows. Rewards stay pending until the previous week is settled.
"""
import calendar
import copy
import json
from datetime import datetime, timedelta, timezone

LIMIT = 20
KEY = 'mng_sb_progress_v1'

# Coin/pack combinations: https://fifauteam.com/fifa-21-squad-battles-rewards/
# Thresholds are local MNG defaults for a 20-match competition, not EA's
# retired worldwide percentiles. They can be overridden in config.json.
# Native crest conversion accepts twelve tiers: 1..3 Elite, 4..6 Gold,
# 7..9 Silver, 10..12 Bronze (CardsDLL 2698e0/269950).
RANKS = [
    ('ELITE_1',9500,1,30000,[404,404]),
    ('ELITE_2',8500,2,15000,[305,403,403]),
    ('ELITE_3',7500,3,12000,[305,305,403]),
    ('GOLD_1',6500,4,11000,[309,303,305]),
    ('GOLD_2',5500,5,11000,[309,305]),
    ('GOLD_3',4500,6,10000,[309,303]),
    ('SILVER_1',3500,7,7000,[303,303]),
    ('SILVER_2',2500,8,4000,[300,301,301]),
    ('SILVER_3',1500,9,1500,[300,301]),
    ('BRONZE_1',800,10,800,[300,300]),
    ('BRONZE_2',400,11,0,[300]),
    ('BRONZE_3',0,12,0,[310]),
]


def rank(s, data):
    thresholds=s.CFG.get('squad_battles_rank_thresholds',{})
    for name,minimum,level,coins,packs in RANKS:
        if data['points'] >= int(thresholds.get(name,minimum)):
            return dict(name=name,level=level,coins=coins,packs=packs)


def claim(s):
    progress(s)  # archive the finished week before looking for pending rewards
    with s.STATE.lock:
        pending=s.STATE.get('mng_sb_pending_weeks',[])
        awards=[]
        s.STATE.conn.execute('BEGIN IMMEDIATE')
        try:
            credits=s.STATE.credits()
            for cycle in pending:
                key='mng_sb_prize_'+str(cycle)
                if s.STATE.get(key):
                    continue
                data=s.STATE.get('mng_sb_week_'+str(cycle))
                if not isinstance(data,dict) or not data.get('scoringMatches'):
                    continue
                reward=rank(s,data)
                credits+=reward['coins']
                for pack in reward['packs']:
                    s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',
                        (pack,json.dumps({'source':'squad_battles','cycle':cycle})))
                s.STATE.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                    (key,json.dumps(reward)))
                entries=[dict(type='coins',value=reward['coins'])] if reward['coins'] else []
                for pack in reward['packs']:
                    entry=s._pack_award(pack)
                    entry.update(isUntradeable=False,untradeable=False)
                    entries.append(entry)
                awards.append(dict(eventId=cycle,awards=entries))
            for key,value in [('credits',credits),('mng_sb_pending_weeks',[])]:
                s.STATE.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))
            s.STATE.conn.commit()
        except Exception:
            s.STATE.conn.rollback()
            raise
        s.PENDING_USERSESSION_REFRESH.set()
        return dict(awardedPrizes=awards,prizesInError=[],credits=credits,
                    awards=[a for prize in awards for a in prize['awards']])


def _offset(utc):
    def transition(month):
        last = calendar.monthrange(utc.year, month)[1]
        day = datetime(utc.year, month, last, 1, tzinfo=timezone.utc)
        return day - timedelta(days=(day.weekday()+1) % 7)
    return 2 if transition(3) <= utc < transition(10) else 1


def window(timestamp):
    utc = datetime.fromtimestamp(timestamp, timezone.utc)
    local = utc + timedelta(hours=_offset(utc))
    sunday = local.replace(hour=10, minute=0, second=0, microsecond=0)
    sunday -= timedelta(days=(local.weekday()+1) % 7)
    if local < sunday:
        sunday -= timedelta(days=7)
    def utc_time(wall):
        # 10:00 is outside the ambiguous/nonexistent DST hours.
        candidate = wall - timedelta(hours=1)
        return int((wall-timedelta(hours=_offset(candidate))).timestamp())
    return utc_time(sunday), utc_time(sunday+timedelta(days=7))


def fresh(cycle):
    return dict(version=2, cycle=cycle, batch=0, played={}, points=0,
                won=0, draw=0, loss=0, totalMatches=0, scoringMatches=0)


def progress(s):
    cycle, end = window(s.now_s())
    with s.STATE.lock:
        raw = s.STATE.get(KEY, {})
        if not isinstance(raw, dict) or not raw:
            return fresh(cycle)
        if raw.get('version') != 2:
            # Preserve this week's legacy daily data, without touching credits.
            legacy_time = int(raw.get('cycle', 0))*86400
            if cycle <= legacy_time < end:
                data = fresh(cycle)
                data.update(copy.deepcopy(raw))
                data.update(version=2, cycle=cycle, batch=0,
                            scoringMatches=min(LIMIT,len(raw.get('played',{}))))
                s.STATE.set(KEY,data)
                return data
            # Archive old results too; no retroactive guessed match credits.
            s.STATE.set('mng_sb_legacy_archive',raw)
            return fresh(cycle)
        if raw.get('cycle') != cycle:
            if int(raw.get('scoringMatches',0)):
                s.STATE.set('mng_sb_week_'+str(raw['cycle']),raw)
                pending=s.STATE.get('mng_sb_pending_weeks',[])
                if raw['cycle'] not in pending:
                    s.STATE.set('mng_sb_pending_weeks',pending+[raw['cycle']])
            data=fresh(cycle)
            s.STATE.set(KEY,data)
            return data
        return repair_scores(s,copy.deepcopy(raw))


def result_key(data, slot):
    return str(slot) if data['batch']==0 else str(data['batch'])+':'+str(slot)


def result(s, slot):
    data=progress(s)
    return data['played'].get(result_key(data,slot))


def refresh(s):
    with s.STATE.lock:
        data=progress(s)
        # Empty repeated requests return the same set. Automatic refresh is
        # intentionally avoided so the final match result remains visible.
        if any(result_key(data,i) in data['played'] for i in range(4)):
            data['batch']+=1
            s.STATE.set(KEY,data)
        return data


def repair_scores(s, data):
    missing={key:entry for key,entry in data['played'].items()
             if entry.get('score',-1)<0 or entry.get('oppScore',-1)<0}
    if not missing:
        return data
    changed=False
    for row in s.STATE.conn.execute("SELECT value FROM kv WHERE key LIKE 'mng_sb_receipt_%'").fetchall():
        try:
            receipt=json.loads(row[0]);response=receipt['response'];payload=receipt['payload']
            own=s.squad_battles_results._goals(payload,'myMatchStats')
            away=s.squad_battles_results._goals(payload,'opponentMatchStats')
            if own<0 or away<0:continue
            for key,entry in missing.items():
                if (int(key.split(':')[-1])==response.get('opponentTeamId') and
                    entry.get('completedAt')==receipt.get('createdAt')):
                    entry.update(score=own,oppScore=away);changed=True
        except (ValueError,TypeError,KeyError):
            continue
    if changed:s.STATE.set(KEY,data)
    return data


def native_ranks(s):
    tiers=[]
    thresholds=s.CFG.get('squad_battles_rank_thresholds',{})
    for index,(name,minimum,level,coins,packs) in enumerate(RANKS):
        minimum=int(thresholds.get(name,minimum))
        maximum=int(thresholds.get(RANKS[index-1][0],RANKS[index-1][1]))-1 if index else 2147483647
        awards=[]
        if coins:
            awards.append(dict(halId=0,assetId=0,awardType='coin',type='coin',
                value=coins,awardValue=coins,count=1,awardCount=1,untradeable=False))
        for pack in packs:
            award=s._pack_award(pack)
            award.update(halId=award['assetId'],untradeable=False,isUntradeable=False)
            awards.append(award)
        # Native view sums rank intervals to display cumulative percentiles.
        # Point thresholds belong exclusively in the Value fields.
        percent_ends=(3,6,10,20,30,40,50,60,70,80,90,100)
        percent_start=1 if index==0 else percent_ends[index-1]+1
        tiers.append(dict(tierLevel=level,tierType=name,tierStart=percent_start,
            tierEnd=percent_ends[index],tierStartValue=minimum,tierEndValue=maximum,awards=awards))
    return tiers


def leaderboard(s):
    data=progress(s)
    entry=dict(persona=str(s.CFG['display_name']),clubName=str(s.CFG['club_name']),
        badge=1,rank=1,score={'value':data['points'],'icon':''},
        tiebreak={'value':data['won'],'icon':''},est=int(s.STATE.get('established',s.now_s())),
        sku='FFA21PC',encryptedData={'encryptedNucleusId':str(s.CFG['persona_id']),
                                    'encryptedPersonaId':str(s.CFG['persona_id'])})
    return {'entries':[entry] if data['scoringMatches'] else []}
