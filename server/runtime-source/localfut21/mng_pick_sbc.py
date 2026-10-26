import remote_assets
"""Owned-squad validation and atomic exchanges for the authored Visca SBC."""
import json
import re

SET=910500
PACK=526
RULES={910101:(85,True)}
PREFIX='mng_pick_80_'
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
    for slot in result['playerRequirements']:
        slot['playerType']='BRICK' if slot['index'] in (0,2,3) else 'NONE'
    result['squad']['squadType']='SBC_SQUAD'
    result['squad']['type']=3
    result['challengeId']=cid
    items=selected(s,cid)
    result['squad'].update(players=[dict(index=index,itemData=s._native_player_item(item)) for index,item in items],
                           rating=rating([item for _,item in items]))
    return result

def save(s,cid,payload):
    raw=payload.get('players',[]) if isinstance(payload,dict) else []
    error_key=PREFIX+'save_error_'+str(cid)
    def reject(reason):
        s.STATE.set(error_key,reason)
        s.log.warning('MNG PICK SQUAD SAVE rejected: %s',reason)
        return 400,{'reason':reason}
    if not isinstance(raw,list):return reject('INVALID_SQUAD')
    slots=[];seen=set();positions=set()
    for fallback,entry in enumerate(raw):
        if not isinstance(entry,dict):return reject('INVALID_PLAYER')
        index=entry.get('index',fallback)
        if type(index) is not int or not 0<=index<23:return reject('INVALID_INDEX')
        # The builder sends the full team, including owned substitutes.
        # Only the eight playable starting slots are exchanged by this SBC.
        if index>=11:continue
        item=entry.get('itemData',entry)
        if not isinstance(item,dict):return reject('INVALID_PLAYER')
        iid=item.get('id',entry.get('itemId',0))
        if type(iid) is not int:return reject('INVALID_ITEM_ID')
        if iid<=0:continue
        if index in (0,2,3):
            # Native locked-slot descriptors are not owned player items.
            if not s.STATE.get_item(iid):continue
            return reject('PLAYER_IN_LOCKED_SLOT')
        if iid in seen or index in positions:return reject('DUPLICATE_SQUAD_SLOT')
        seen.add(iid);positions.add(index);slots.append(dict(index=index,itemId=iid))
    with s.STATE.lock:
        s.STATE.set(PREFIX+'squad_'+str(cid),slots)
        s.STATE.set(error_key,None)
    s.log.info('MNG PICK SQUAD SAVE accepted: received=%s starters=%s',len(raw),len(slots))
    return 200,{}


def submit(s,cid):
    with s.STATE.lock:
        key=PREFIX+'receipt_'+str(cid)
        previous=s.STATE.get(key)
        pairs=selected(s,cid);items=[item for _,item in pairs]
        if s.STATE.get(PREFIX+'save_error_'+str(cid)):
            return 400,{'reason':'The latest squad could not be saved. Reopen the SBC before submitting.'}
        if not items and previous:return 200,previous
        completed=int(s.STATE.get(PREFIX+'completed',0) or 0)
        def invalid(message):
            return 200,dict(id=cid,challengeId=cid,setId=SET,success=False,valid=False,
                            completed=False,status='INVALID',message=message)
        if completed>=10:return invalid('La limite de 10 réalisations est atteinte.')
        if len(items)!=8:return invalid('8 joueurs or sont nécessaires.')
        if any(item.get('itemType','player')!='player' or int(item.get('loans',0) or 0)>0 or item.get('concept') or item.get('dream') for item in items):
            return invalid('Les joueurs de prêt et concepts ne peuvent pas être échangés.')
        if len({int(item.get('assetId',item['resourceId'])) for item in items})!=8:
            return invalid('Les 8 joueurs doivent être différents.')
        if any(int(item.get('rating',0))<75 for item in items):return invalid('Les 8 joueurs doivent être or.')
        if sum(int(item.get('rareflag',0))==1 for item in items)<2:return invalid('Au moins 2 joueurs or rares sont nécessaires.')
        ids={int(item['id']) for item in items}
        for iid in ids:
            row=s.STATE.conn.execute('SELECT pile FROM items WHERE id=?',(iid,)).fetchone()
            if not row or row[0] not in ('club','unassigned','squad'):return invalid('Un joueur sélectionné n’est plus disponible.')
        done=s._sbc_completed()
        challenge=s._SBC_CHAL_BY_INT[cid]
        if completed+1>=10:done.add(str(challenge['id']))
        set_obj=s._SBC_SET_BY_INT[SET]
        complete=all(str(c['id']) in done for c in set_obj['challenges'])
        granted=[token(s)]
    # Native eligibility advertises 60 chemistry; no invented server-side
        # chemistry formula. The game evaluates this alongside its lineup.
        pack_count=len(s.STATE.unopened_pack_ids())
        response=dict(id=cid,challengeId=cid,setId=SET,success=True,valid=True,completed=True,status='COMPLETED',
            timesCompleted=completed+1,repeatable=completed+1<10,grantedChallengeAwards=s._sbc_awards(challenge),grantedSetAwards=[],
            awards=[],rewards=[],credits=s.STATE.credits(),grantedItemsCount=len(granted),grantedItems=granted,
            itemData=granted,preOrderPacks=pack_count,recoveredPacks=0,
            unopenedPacks=pack_count)
        for award in response['grantedChallengeAwards']:
            if award.get('type')=='item':award['itemData']=s._native_pack_item(granted[0])
        # Selected players, reward token, completion and receipt commit together.
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
            insert_token(s,granted[0])
            _put(s,'sbc_completed',sorted(done))
            _put(s,PREFIX+'squad_'+str(cid),[])
            _put(s,key,response)
            _put(s,PREFIX+'completed',completed+1)
        s.PENDING_USERSESSION_REFRESH.set()
        return 200,response

def route(s,method,path,payload):
    m=re.fullmatch(r'/ut/game/fifa21/sbs/challenge/(910501)(/squad)?',path)
    if not m:return None
    cid=int(m.group(1))
    if m.group(2) and method=='PUT':return save(s,cid,payload)
    if not m.group(2) and method=='PUT':return submit(s,cid)
    return 200,view(s,cid)


def presentation(s,body):
    count=int(s.STATE.get(PREFIX+'completed',0) or 0)
    body.update(repeatable=count<10,timesCompleted=count)
    body['description']=str(body.get('description',''))+'\nRéalisations : '+str(count)+'/10.'
    if count<10:
        body.update(status='NOT_STARTED',isCompleted=False,challengesCompletedCount=0)
    return body

def token(s):
    min_rating=80;choice_count=3;pile='unassigned';source_pack_id=526
    candidates=[r for r,p in s.PLAYER_DB.items() if int(p.get('rating',0))>=80 and p.get('packEligible',True) and s.aqua_pro_resource_id(r) is None]
    if len(candidates)<3:raise ValueError('Insufficient 80+ pick candidates')
    preview_resource_id=s.random.choice(candidates)
    item_id=s.STATE.next_item_id()
    name = f"1 of {choice_count} {min_rating}+ Player Pick"
    preview_resource_id = int(preview_resource_id or 0)
    item = {
        "id": item_id,
        "timestamp": s.now_s(),
        "resourceId": preview_resource_id,
        "assetId": preview_resource_id,
        "carddbid": preview_resource_id,
        "cardassetid": 34,
        "itemType": "misc",
        # FIFA 21/current FUT clients identify a player-pick token by the
        # misc-card subtype, not by a one-player pack definition.
        "cardsubtypeid": 237,
        "subtype": 237,
        "subType": 237,
        "itemState": "free",
        "stackCount": 1,
        "untradeableCount": 1,
        "untradeable": True,
        "owners": 1,
        "pile": pile,
        "rating": min_rating,
        "rareflag": 1,
        "discardValue": 0,
        "name": name,
        "description": f"Choose one of {choice_count} players rated {min_rating} or higher.",
        "IS_UNLOCKABLE": True,
        "UNLOCKABLE_TYPE": "PLAYER_PICK",
        # CardWrapper has a dedicated UNLOCKS/EMPTY_UNLOCKS renderer. A
        # player-pick token is not a player catalog row, so marking this as
        # PLAYER makes resourceId 0 render as the grey placeholder.
        "CARD_TYPE": "UNLOCKS",
        "cardType": "UNLOCKS",
        "card_type": "UNLOCKS",
        "UNLOCKS": [],
        "choiceCount": choice_count,
        "minRating": min_rating,
        "sourcePackId": int(source_pack_id or 0),
        "resourceGameYear": 2021,
    }
    item.update(name='Choix joueur 80+ (1 sur 3)',description='1/3',rareflag=23)
    return item

def insert_token(s,item):
    s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',(item['id'],item['resourceId'],'unassigned',json.dumps(item)))
    _put(s,'player_pick:'+str(item['id']),dict(minRating=80,choiceCount=3,choices=[]))

def migrate_pending(s):
    with s.STATE.lock:
        rows=s.STATE.conn.execute('SELECT id FROM unopened_packs WHERE pack_id=526').fetchall()
        items=[token(s) for row in rows]
        with s.STATE.conn:
            for row,item in zip(rows,items):
                insert_token(s,item)
                s.STATE.conn.execute('DELETE FROM unopened_packs WHERE id=?',(row['id'],))
        with s.STATE.conn:
            for row in s.STATE.conn.execute("SELECT id,data FROM items WHERE pile='unassigned'").fetchall():
                item=json.loads(row['data'])
                if item.get('itemType')=='misc' and (item.get('UNLOCKABLE_TYPE')=='PLAYER_PICK' or int(item.get('subtype',0))==237 or int(item.get('cardsubtypeid',0))==237):
                    count=max(2,min(5,int(item.get('choiceCount',3))))
                    item.update(cardsubtypeid=237,subtype=237,subType=237,rareflag=23,
                                rating=int(item.get('minRating',80)),discardValue=0,
                                CARD_TYPE='UNLOCKS',cardType='UNLOCKS',card_type='UNLOCKS')
                    item.pop('attributeList',None)
                    item['description']=f'1/{count}' 
                    s.STATE.conn.execute('UPDATE items SET data=? WHERE id=?',(json.dumps(item),row['id']))
        if rows:s.log.info('Converted %s unopened 80+ packs into direct player picks',len(rows))



def grant_requested_five(s):
    key='mng_direct_five_picks_20261026_1204_v1'
    with s.STATE.lock:
        if s.STATE.get(key):return
        items=[token(s) for _ in range(5)]
        with s.STATE.conn:
            for item in items:insert_token(s,item)
            _put(s,key,{'itemIds':[item['id'] for item in items],'count':5})
        s.log.info('Granted five user-requested 80+ player picks: %s',[item['id'] for item in items])
