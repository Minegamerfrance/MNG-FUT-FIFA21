"""Server-clock release gates; no club migration or destructive state changes."""
from datetime import datetime,timezone
import re,time,urllib.parse

# Paris is UTC+1 on both requested November release dates.
STARTS={'totw1':int(datetime(2026,11,4,19,tzinfo=timezone.utc).timestamp()),
        'rulebreakers':int(datetime(2026,11,6,19,tzinfo=timezone.utc).timestamp())}
RARITIES={3:'totw1',22:'rulebreakers'}
OBJECTIVES={7101,7102,8003}

def active(event,now=None):return (time.time() if now is None else now)>=STARTS[event]
def available(meta):
    event=RARITIES.get(int(meta.get('rareflag',0)))
    return event is None or active(event)
def pack_event(cfg):
    flags=set(cfg.get('allowed_rareflags',[]))
    for rarity,event in RARITIES.items():
        if flags=={rarity} and not active(event):return event
    return None
def unavailable(s,event):
    return 403,{'Cache-Control':'no-store'},s.json_bytes(dict(reason='EVENT_NOT_STARTED',event=event,startTime=STARTS[event]))

def apply(s):
    if getattr(s,'_event_schedule_applied',False):return
    s._event_schedule_applied=True
    hidden_sets={sid for sid,obj in s._SBC_SET_BY_INT.items() if int(obj.get('tabId',0))==9}
    hidden_challenges={cid for cid,obj in s._SBC_CHAL_BY_INT.items() if int(obj.get('_setInt',0)) in hidden_sets}
    original_sets=s._sbc_sets_response
    def sets():
        result=original_sets()
        if not active('rulebreakers'):result['categories']=[c for c in result['categories'] if c['categoryId']!=9]
        return result
    s._sbc_sets_response=sets
    original_campaign=s._scmp_campaign_json
    def campaign():
        result=original_campaign()
        if not active('rulebreakers'):
            for key in ('scmpCategoryProgressList','categoriesList','categories'):
                result[key]=[c for c in result[key] if c['categoryId']!=71]
        return result
    s._scmp_campaign_json=campaign
    original_pack=s.get_pack_cfg
    def pack_cfg(pid):
        cfg=original_pack(pid)
        if not pack_event(cfg) and isinstance(cfg.get('allowed_rareflags'),list):
            cfg['allowed_rareflags']=[r for r in cfg['allowed_rareflags'] if r not in RARITIES or active(RARITIES[r])]
        elif pack_event(cfg):cfg['enabled']=False
        return cfg
    s.get_pack_cfg=pack_cfg
    original_create=s.State.create_pack
    def create(state,pid,*args,**kwargs):
        event=pack_event(s.get_pack_cfg(pid))
        if event:raise ValueError('EVENT_NOT_STARTED: '+event)
        return original_create(state,pid,*args,**kwargs)
    s.State.create_pack=create
    original_route=s.route_fut
    def route(method,raw_path,headers,body):
        parsed=urllib.parse.urlsplit(raw_path);path=s.season_persistence.normalize('/'+parsed.path.lstrip('/').lower().rstrip('/'))
        query=urllib.parse.parse_qs(parsed.query);payload=s.safe_json(body)
        if not active('rulebreakers'):
            match=re.fullmatch(r'/ut/game/fifa21/sbs/(challenge|setid)/(\d+)(?:/.*)?',path)
            if match and int(match.group(2)) in (hidden_challenges if match.group(1)=='challenge' else hidden_sets):return unavailable(s,'rulebreakers')
            if re.fullmatch(r'/ut/game/fifa21/scmp/(?:active|learning|world)/category/71/details',path):
                return 200,{'Cache-Control':'no-store'},s.json_bytes(dict(categoryId=71,groupsList=[]))
            match=re.search(r'/scmp/(?:campaign/)?group/(\d+)',path)
            if match and int(match.group(1)) in OBJECTIVES:return unavailable(s,'rulebreakers')
        event=None
        match=re.fullmatch(r'/ut/game/fifa21/(?:featuredsquad|sqbt/user/opponentsquad)/(4|5)',path)
        if match:event='totw1' if match.group(1)=='4' else 'rulebreakers'
        if path=='/ut/game/fifa21/match' and method in ('POST','PUT'):
            slot=s._requested_sqbt_opponent(payload)
            if slot in (4,5):event='totw1' if slot==4 else 'rulebreakers'
        if event and not active(event):return unavailable(s,event)
        if path.startswith('/ut/game/fifa21/featuredsquad/user/stats'):
            consumer=query.get('featureConsumerId',[''])[0]
            event={'sqbt':'rulebreakers','sqbttotw':'totw1'}.get(consumer)
            if event and not active(event):
                return 200,{'Cache-Control':'no-store'},s.json_bytes(dict(id=0,squadId=0,featuredSquadId=0,available=False,enabled=False,isActive=False,
                    startTime=STARTS[event],endTimeStamp=STARTS[event],pointsWon=-1,score=-1,oppScore=-1,bannerImageName='',difficultyBasedWinPoints=[],difficultyBasedLossPoints=[],sqbt2data={}))
        if path=='/ut/game/fifa21/purchased/items' and method in ('POST','PUT'):
            request=s._purchase_request_document(payload,headers,body,query)
            try:event=pack_event(s.get_pack_cfg(s._purchase_pack_id(request)))
            except (ValueError,TypeError):event=None
            if event:return unavailable(s,event)
        return original_route(method,raw_path,headers,body)
    s.route_fut=route
