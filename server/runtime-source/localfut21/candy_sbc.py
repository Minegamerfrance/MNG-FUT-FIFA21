import remote_assets
"""Owned-squad validation and atomic exchanges for the authored Visca SBC."""
import json
import re

SET=910100
PACK=523
RULES={910101:(85,True)}
PREFIX='rulebreakers_candy_'
BADGES={'330003-mng83-v1','330004-1f4ce31f-188f','330005-fb83431f-9d46'}

def asset(s,method,path):
    if path in ('/fut/packs/images/background_51.dds',
                '/contentfifa/ui/external/ion_fut/imgassets/pack/background/background_51.dds'):
        return 200,{'Content-Type':'image/vnd-ms.dds','Cache-Control':'no-store'},remote_assets.read((s.ROOT/'custom-packimages/background_51.dds'))
    if path != '/fut/sbc/gen4/sets/images/sbc_set_image_1010005.png':return None
    return 200,{'Content-Type':'image/png','Cache-Control':'no-store'},remote_assets.read((s.ROOT/'assets/sbc/sbc_set_image_1010005.png'))

def rating(items):
    if len(items)!=11:return 0
    values=[int(x.get('rating',0)) for x in items]
    total=sum(values)
    # Sum plus above-average correction, rounded before division by 11.
    scaled=total*11+sum(max(0,v*11-total) for v in values)
    return ((scaled+5)//11)//11

def _put(s,key,value):
    s.STATE.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))

def selected(s,cid):
    slots=s.STATE.get(PREFIX+'squad_'+str(cid),[])
    result=[]
    for slot in slots:
        item=s.STATE.get_item(slot['itemId'])
        if item:result.append((slot['index'],item))
    return result

def view(s,cid):
    result=s._sbc_empty_squad(cid)
    items=selected(s,cid)
    result['squad'].update(players=[dict(index=index,itemData=s._native_player_item(item)) for index,item in items],
                           rating=rating([item for _,item in items]))
    return result

def save(s,cid,payload):
    raw=payload.get('players',[]) if isinstance(payload,dict) else []
    if not isinstance(raw,list):return 400,{'reason':'INVALID_SQUAD'}
    slots=[];seen=set();positions=set()
    for fallback,entry in enumerate(raw):
        if not isinstance(entry,dict):return 400,{'reason':'INVALID_PLAYER'}
        item=entry.get('itemData',entry)
        if not isinstance(item,dict):return 400,{'reason':'INVALID_PLAYER'}
        index=entry.get('index',fallback)
        iid=item.get('id',entry.get('itemId',0))
        if not iid:continue
        if type(iid) is not int or type(index) is not int or not 0<=index<11 or iid in seen or index in positions:
            return 400,{'reason':'INVALID_SQUAD_SLOTS'}
        seen.add(iid);positions.add(index);slots.append(dict(index=index,itemId=iid))
    with s.STATE.lock:s.STATE.set(PREFIX+'squad_'+str(cid),slots)
    return 200,{}

def submit(s,cid):
    with s.STATE.lock:
        key=PREFIX+'receipt_'+str(cid)
        previous=s.STATE.get(key)
        if previous:return 200,previous
        pairs=selected(s,cid);items=[item for _,item in pairs]
        def invalid(message):
            return 200,dict(id=cid,challengeId=cid,setId=SET,success=False,valid=False,
                            completed=False,status='INVALID',message=message)
        if not any(int(p.get('rareflag',0))==22 and p.get('packEligible',True) for p in s.PLAYER_DB.values()):
            return invalid('Le contenu du pack Rulebreakers est encore en préparation.')
        if len(items)!=11:return invalid('11 joueurs possédés sont nécessaires.')
        if any(item.get('itemType','player')!='player' or int(item.get('loans',0) or 0)>0 or item.get('concept') or item.get('dream') for item in items):
            return invalid('Les joueurs de prêt et concepts ne peuvent pas être échangés.')
        if len({int(item.get('assetId',item['resourceId'])) for item in items})!=11:
            return invalid('Les 11 joueurs doivent être différents.')
        required,totw=RULES[cid]
        if rating(items)<required:return invalid(f'Note d’équipe minimale : {required}.')
        if totw and not any(int(item.get('rareflag',0))==3 for item in items):
            return invalid('Au moins un joueur TOTW est obligatoire.')
        ids={int(item['id']) for item in items}
        for iid in ids:
            row=s.STATE.conn.execute('SELECT pile FROM items WHERE id=?',(iid,)).fetchone()
            if not row or row[0] not in ('club','unassigned','squad'):return invalid('Un joueur sélectionné n’est plus disponible.')
        done=s._sbc_completed()
        challenge=s._SBC_CHAL_BY_INT[cid]
        done.add(str(challenge['id']))
        set_obj=s._SBC_SET_BY_INT[SET]
        complete=all(str(c['id']) in done for c in set_obj['challenges'])
        granted=[]
    # Native eligibility advertises 60 chemistry; no invented server-side
        # chemistry formula. The game evaluates this alongside its lineup.
        pack_count=len(s.STATE.unopened_pack_ids())+1
        response=dict(id=cid,challengeId=cid,setId=SET,success=True,valid=True,completed=True,status='COMPLETED',
            timesCompleted=1,grantedChallengeAwards=s._sbc_awards(challenge),grantedSetAwards=[],
            awards=[],rewards=[],credits=s.STATE.credits(),grantedItemsCount=len(granted),grantedItems=granted,
            itemData=granted,preOrderPacks=pack_count,recoveredPacks=0,
            unopenedPacks=pack_count)
        # Selected players, completion, final card and replay receipt commit together.
        with s.STATE.conn:
            for iid in ids:s.STATE.conn.execute('DELETE FROM items WHERE id=?',(iid,))
            for row in s.STATE.conn.execute('SELECT id,data FROM squads').fetchall():
                squad=json.loads(row['data']);old=squad.get('players',[])
                def item_id(slot):
                    return slot.get('itemId',slot.get('itemData',{}).get('id',slot.get('id',0))) if isinstance(slot,dict) else 0
                kept=[slot for slot in old if item_id(slot) not in ids]
                if kept!=old:
                    squad['players']=kept
                    s.STATE.conn.execute('UPDATE squads SET data=? WHERE id=?',(json.dumps(squad),row['id']))
            s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',
                (PACK,json.dumps({'source':'rulebreakers_candy_sbc','challengeId':cid,'created':s.now_s(),'untradeable':True})))
            _put(s,'sbc_completed',sorted(done))
            _put(s,PREFIX+'squad_'+str(cid),[])
            _put(s,key,response)
        s.PENDING_USERSESSION_REFRESH.set()
        return 200,response

def route(s,method,path,payload):
    m=re.fullmatch(r'/ut/game/fifa21/sbs/challenge/(910101)(/squad)?',path)
    if not m:return None
    cid=int(m.group(1))
    if m.group(2) and method=='PUT':return save(s,cid,payload)
    if not m.group(2) and method=='PUT':return submit(s,cid)
    return 200,view(s,cid)
