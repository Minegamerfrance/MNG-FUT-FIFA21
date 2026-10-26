"""Shared catalogue search and a persistent local FUT transfer market."""
import copy
import datetime
import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

CONCEPT_BASE=600000000000
MARKET_BASE=700000000000

def number(value,default=0):
    try:return int(value)
    except (ValueError,TypeError):return default

def criteria(query,payload):
    result={str(k).lower():v[-1] for k,v in query.items() if v}
    if isinstance(payload,dict):
        for key in ['searchCriteria','criteria','filters']:
            if isinstance(payload.get(key),dict):result.update({str(k).lower():v for k,v in payload[key].items()})
        result.update({str(k).lower():v for k,v in payload.items() if not isinstance(v,dict)})
    return result

def value(search,*keys,default=None):
    return next((search[k.lower()] for k in keys if k.lower() in search),default)

def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFD',str(text)).lower() if not unicodedata.combining(c))

def ids(raw):
    if isinstance(raw,list):return {number(x) for x in raw}
    return {int(x) for x in re.findall(r'\d+',str(raw or ''))}

def filter_items(items,search,resolve_item=None):
    items=list(items)
    excluded=ids(value(search,'exclitem','excludeItems','excludeItemIds'))
    excluded_defs=ids(value(search,'excldef','excludeDefIds'))
    # A squad excludes owned item IDs, but another copy/version of that
    # player cannot be selected either. Keep the inventory intact and hide
    # those copies only while an exclusion list is supplied by the client.
    excluded_items=[item for item in items if number(item.get('id')) in excluded]
    if resolve_item is not None:
        excluded_items.extend(item for iid in excluded if iid>0
                              for item in [resolve_item(iid)] if item)
    excluded_players={number(item.get('assetId'),number(item.get('resourceId')) & 0xffffff)
                      for item in excluded_items
                      if item.get('itemType','player')=='player'} - {0}
    wanted_type=folded(value(search,'type','itemType',default='player'))
    category=folded(value(search,'cat','category',default=''))
    if wanted_type in ('staff','managers'):wanted_type='manager'
    if wanted_type in ('development','consumable','consumables'):wanted_type='training'
    if wanted_type in ('clubinfo','clubitems','clubitem'):wanted_type='badge' if category in ('badge','badges','11') else 'kit'
    if wanted_type in ('concept','conceptplayer'):wanted_type='player'
    # Native name selection sends a comma-separated vector of definitions,
    # padded with zeroes; web searches may use a scalar or JSON array.
    player_definitions={x for x in ids(value(search,'defid','definitionid','resourceid')) if x>0}
    player_assets={x for x in ids(value(search,'maskeddefid','assetid')) if x>0}
    result=[]
    for item in items:
        kind=item.get('itemType','player')
        if kind=='custom' and number(item.get('cardsubtypeid'))==11:kind='badge'
        if wanted_type not in ('any','all','',kind):continue
        if wanted_type=='training':
            family=category.replace('_','').replace('-','');effect=item.get('effect')
            if family in ('playstyle','playerplaystyle','chemistrystyle') and (effect!='style' or number(item.get('playStyle'))>=19):continue
            if family in ('gkplaystyle','goalkeeperplaystyle') and (effect!='style' or number(item.get('playStyle'))<19):continue
            if family in ('league','managerleague','managerleaguemodifier') and effect!='league':continue
            if family in ('position','positionmodifier') and effect!='position':continue
            if family in ('healing','heal','injury','playerhealing') and effect!='healing':continue
            if family in ('contract','contracts','playercontract','managercontract'):
                if effect!='contract':continue
                if family=='playercontract' and number(item.get('cardsubtypeid'))!=201:continue
                if family=='managercontract' and number(item.get('cardsubtypeid'))!=202:continue

        subtype=number(value(search,'cardsubtype','cardsubtypeid','subtype'))
        if subtype and subtype!=number(item.get('cardsubtypeid')):continue
        if number(item.get('id')) in excluded or number(item.get('resourceId')) in excluded_defs:continue
        if kind=='player' and number(item.get('assetId'),number(item.get('resourceId')) & 0xffffff) in excluded_players:continue
        if player_definitions and number(item.get('resourceId')) not in player_definitions:continue
        if player_assets and number(item.get('assetId')) not in player_assets:continue
        checks=[(('leag','league','leagueid'),('leagueId',)),(('team','club','teamid'),('teamid',)),
                (('nat','nationality','nation'),('nation',))]
        if any(number(value(search,*names))>0 and number(value(search,*names)) not in [number(item.get(k)) for k in fields] for names,fields in checks):continue
        position=str(value(search,'pos','position',default='')).upper()
        if position not in ('','ANY'):
            if kind=='training' and item.get('effect')=='position':
                modifier=str(item.get('positionModifier') or (str(item.get('sourcePosition',''))+'-'+str(item.get('targetPosition','')))).upper()
                if position!=modifier:continue
            elif str(item.get('preferredPosition','')).upper()!=position:continue
        rating=number(item.get('rating'))
        if rating<number(value(search,'minrating','ratingmin')) or rating>number(value(search,'maxrating','ratingmax'),99):continue
        level=str(value(search,'level','lev',default='')).lower()
        tier='gold' if rating>=75 else 'silver' if rating>=65 else 'bronze'
        if level in ('gold','silver','bronze') and tier!=level:continue
        rare=str(value(search,'rare',default='')).upper()
        rf=number(item.get('rareflag'))
        if rare in ('SP','SPECIAL') and rf<=1:continue
        if rare in ('RARE','R') and rf!=1:continue
        if rare in ('COMMON','C') and rf!=0:continue
        rarity=value(search,'rarity','rareflag')
        if rarity is not None and number(rarity,-1)>=0 and rf!=number(rarity):continue
        name=folded(value(search,'name','search','query',default=''))
        if name and name not in folded(' '.join(str(item.get(k,'')) for k in ['name','firstName','lastName','commonname'])):continue
        if number(item.get('weakFoot'))<number(value(search,'minweakfoot')):continue
        if number(item.get('skillMoves'))<number(value(search,'minskillmoves')):continue
        result.append(item)
    sort=str(value(search,'sortby',default='ovr')).lower()
    field={'price':'buyNowPrice','value':'buyNowPrice','name':'name','rating':'rating','ovr':'rating'}.get(sort,'rating')
    result.sort(key=lambda x:(str(x.get(field,'')) if field=='name' else number(x.get(field)),number(x.get('resourceId')),number(x.get('id'))),reverse=str(value(search,'sort',default='desc')).lower()!='asc')
    return result

def page(items,search):
    count=max(1,min(100,number(value(search,'count','num','pagesize'),12)))
    start=max(0,number(value(search,'start','offset','startindex')))
    if not start and value(search,'page') is not None:start=max(0,number(value(search,'page'),1)-1)*count
    return items[start:start+count]

def eligible(meta):
    return meta.get('catalogEnabled',True) and meta.get('packEligible',True) and str(meta.get('acquisition','')).lower() not in ('sbc','objective','objectives')

def cosmetics(s):
    result=[]
    team_leagues={number(p.get('teamid')):number(p.get('leagueId')) for p in s.PLAYER_DB.values()}
    for k in s.KIT_DB:
        if number(k.get('kitType'),-1) not in (0,1,2,3):continue
        rid=number(k['resourceId']);kind=number(k['kitType'])
        result.append(dict(resourceId=rid,assetId=rid,carddbid=rid,cardassetid=35,itemType='kit',
                           cardsubtypeid=9,family='kits',table='fcc_kitcards',name=k['name'],teamid=number(k.get('teamid')),
                           leagueId=number(k.get('leagueId'),team_leagues.get(number(k.get('teamid')),0)),kitType=kind,teamkittypetechid=kind,
                           category=2+kind,year=0,rating=75,rareflag=1,discardValue=30,value=75,weightrare=10,islocked=0))
    badge_file=Path(s.__file__).parent/'badges.json'
    for badge in json.loads(badge_file.read_text(encoding='utf-8')):
        result.append(dict(badge,itemType='custom',family='badges',table='fcc_badgecards',cardsubtypeid=11,cardassetid=39,
                           category=1,rating=75,rareflag=1,discardValue=30,value=75,weightrare=10,islocked=0))
    return result

def cosmetic_item(meta,item_id,pile='unassigned'):
    return dict(meta,id=item_id,pile=pile,itemState='free',owners=1,untradeable=False,
                stackCount=1,untradeableCount=0,lastSalePrice=0,resourceGameYear=2021)

def consumables(s):
    return json.loads((Path(s.__file__).parent/'consumables.json').read_text(encoding='utf-8'))

def catalogue(s,search,concept=False):
    kind=str(value(search,'type','itemType',default='player')).lower()
    if kind in ('player','concept','conceptplayer','any','all'):
        result=[]
        for rid,meta in s.PLAYER_DB.items():
            if not meta.get('catalogEnabled',True):continue
            if not concept and not eligible(meta):continue
            item=s.STATE.build_player_item(rid,CONCEPT_BASE+rid if concept else MARKET_BASE+rid,'concept' if concept else 'trade')
            item.update(name=meta.get('name',''))
            if concept:item.update(concept=True,dream=True,untradeable=True,contract=0,contracts=0)
            result.append(item)
        return result
    if kind in ('staff','manager','managers'):
        return [s.STATE.build_manager_item(rid,MARKET_BASE+rid,'trade') for rid in s.MANAGER_DB]
    if kind in ('development','consumable','consumables','training'):
        return [cosmetic_item(m,MARKET_BASE+number(s.STATE.get('market_generation_'+str(m['resourceId']),0))*1000000000+number(m['resourceId']),'trade') for m in consumables(s)]
    return [cosmetic_item(m,MARKET_BASE+number(m['resourceId']),'trade') for m in cosmetics(s)]

def local_price(item):
    if item.get('itemType')!='player':return 500 if item.get('itemType')=='manager' else 300
    r=number(item.get('rating'))
    if number(item.get('rareflag'))==12:return max(50000,(r-70)**3*20//50*50)
    base=200 if r<65 else 400 if r<75 else max(650,(r-72)**3*10//50*50)
    return base*2 if number(item.get('rareflag'))>1 else base

def apply_consumable(s,rid,target_id):
    meta=next((m for m in consumables(s) if m['resourceId']==rid),None)
    if not meta or meta['effect']=='position':return None
    state=s.STATE
    with state.lock:
        owned=next((x for x in state.list_items('club') if x.get('resourceId')==rid),None)
        target=state.get_item(target_id)
        recover_squad_card = bool(target and target.get('pile')=='trade' and target.get('itemState','free')=='free'
                                  and target_id in referenced_ids(state.list_squads()))
        if not target or (target.get('pile') not in ('club','squad') and not recover_squad_card):
            return 400,{'reason':'Consumable or target is not owned in the club'}
        if recover_squad_card:target['pile']='club'
        if not owned:
            current=number(target.get('playStyle'))
            if current>=250:current-=250
            if meta['effect']=='style' and current==meta['playStyle']:
                return 200,{'itemData':[s._native_pack_item(target)],'consume':False,'applyTo':target_id,'resourceId':rid}
            return 400,{'reason':'Consumable is not owned in the club'}

        kind=target.get('itemType')
        effect=meta['effect']
        if effect=='contract':
            required='player' if meta['cardsubtypeid']==201 else 'manager'
            if kind!=required:return 400,{'reason':'Wrong contract target'}
            rating=number(target.get('rating'));tier='gold' if rating>=75 else 'silver' if rating>=65 else 'bronze'
            target['contract']=target['contracts']=min(99,number(target.get('contract'))+meta['contractBonus'][tier])
        elif effect=='healing':
            if kind!='player':return 400,{'reason':'Healing requires a player'}
            games=number(target.get('injuryGames'))
            if games<=0:return 400,{'reason':'Player is not injured'}
            target['injuryGames']=max(0,games-number(meta['amount']))
            if not target['injuryGames']:target['injuryType']='none'
        elif effect=='style':
            if kind!='player':return 400,{'reason':'Style requires a player'}
            is_gk=target.get('preferredPosition')=='GK'
            if is_gk!=(meta['playStyle']>=19):return 400,{'reason':'Goalkeeper/outfield style does not match'}
            current=number(target.get('playStyle'))
            if current>=250:current-=250
            if current==meta['playStyle']:
                return 200,{'itemData':[s._native_pack_item(target)],'consume':False,'applyTo':target_id,'resourceId':rid}
            target['playStyle']=meta['playStyle']
        elif effect=='league':
            if kind!='manager':return 400,{'reason':'League modifier requires a manager'}
            target['leagueId']=meta['leagueId']
        with state.conn:
            state.conn.execute('UPDATE items SET pile=?,data=? WHERE id=?',(target.get('pile','club'),json.dumps(target),target_id))
            count=max(1,number(owned.get('stackCount'),1))
            if count>1:
                owned['stackCount']=count-1
                owned['untradeableCount']=min(count-1,number(owned.get('untradeableCount')))
                state.conn.execute('UPDATE items SET data=? WHERE id=?',(json.dumps(owned),owned['id']))
            else:state.conn.execute('DELETE FROM items WHERE id=?',(owned['id'],))
        s.log.info('Applied owned consumable resource=%s target=%s recoveredSquadCard=%s',rid,target_id,recover_squad_card)
        return 200,{'itemData':[s._native_pack_item(target)],'consume':True,'applyTo':target_id,'resourceId':rid}

def auction(s,item):
    rid=number(item['resourceId']);generation=number(s.STATE.get('market_generation_'+str(rid),0))
    price=local_price(item)
    trade=MARKET_BASE+generation*1000000000+rid
    return dict(tradeId=trade,itemData=item,buyNowPrice=price,startingBid=price,currentBid=0,
                offers=0,expires=3600,tradeState='active',bidState='none',watched=False,sellerName='MNG FUT',sellerEstablished=0)

def buy(s,trade_id,bid):
    state=s.STATE
    with state.lock:
        receipt=state.get('market_receipt_'+str(trade_id))
        if receipt:return 200,receipt
        delta=trade_id-MARKET_BASE
        if delta<0:return 404,{'reason':'Unknown auction'}
        rid=delta%1000000000;generation=delta//1000000000
        if generation!=number(state.get('market_generation_'+str(rid),0)):return 409,{'reason':'Auction expired'}
        if rid in s.PLAYER_DB and eligible(s.PLAYER_DB[rid]):item=state.build_player_item(rid,0,'unassigned')
        elif rid in s.MANAGER_DB:item=state.build_manager_item(rid,0,'unassigned')
        else:
            meta=next((m for m in cosmetics(s)+consumables(s) if number(m['resourceId'])==rid),None)
            if meta is None:return 404,{'reason':'Unknown auction'}
            item=cosmetic_item(meta,0)
        price=local_price(item)
        if bid<price:return 400,{'reason':'Bid below local buy-now price'}
        if state.credits()<price:return 458,{'reason':'Not enough credits'}
        state.conn.execute('BEGIN IMMEDIATE')
        try:
            # No helper that commits may run inside this purchase transaction.
            row=state.conn.execute("SELECT value FROM kv WHERE key='next_item_id'").fetchone()
            # Native buy-to-apply tracks the listed consumable's item ID.
            # Preserve it when ownership changes, including repeat listings.
            iid=trade_id if item.get('itemType')=='training' else number(json.loads(row[0]))+1
            item.update(id=iid,lastSalePrice=price,timestamp=s.now_s(),marketPurchase=True)
            if item.get('itemType')=='player' and rid in state.owned_player_resource_ids():item.update(duplicate=True,isDuplicate=True)
            remaining=state.credits()-price
            entry=auction(s,item);entry.update(tradeId=trade_id,tradeState='closed',bidState='buyNow',currentBid=price,expires=-1)
            response={'auctionInfo':[entry],'credits':remaining,'itemData':[item]}
            for key,val in [('credits',remaining),('next_item_id',max(number(json.loads(row[0])),iid)),('market_generation_'+str(rid),generation+1),('market_receipt_'+str(trade_id),response)]:
                state.conn.execute('INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)',(key,json.dumps(val)))
            state.conn.execute('INSERT INTO items VALUES(?,?,?,?)',(iid,rid,'unassigned',json.dumps(item)))
            state.conn.commit()
        except Exception:
            state.conn.rollback();raise
        return 200,response

def owned_listing(s,item,data=None):
    data=data if data is not None else s.STATE.get('owned_auction_'+str(item['id']))
    if not isinstance(data,dict) or item.get('pile')!='trade':return None
    seconds=max(-1,int(data['expiresAt'])-s.now_s())
    active=seconds>0
    return dict(tradeId=int(data['tradeId']),itemData=s._native_pack_item(item),
        startingBid=int(data['startingBid']),buyNowPrice=int(data['buyNowPrice']),currentBid=0,
        offers=0,expires=seconds,tradeState='active' if active else 'expired',bidState='none',watched=False)


def list_owned(s,payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('itemData'),dict):return 400,{'reason':'INVALID_LISTING'}
    iid=number(payload['itemData'].get('id'));start=number(payload.get('startingBid'));buy_now=number(payload.get('buyNowPrice'));duration=number(payload.get('duration'))
    if duration not in (3600,10800,21600,43200,86400,259200):return 400,{'reason':'INVALID_DURATION'}
    if start<150 or buy_now<start or buy_now>15000000:return 400,{'reason':'INVALID_PRICE_RANGE'}
    state=s.STATE
    with state.lock:
        item=state.get_item(iid)
        if not item or item.get('pile')!='trade' or item.get('untradeable') or number(item.get('loans'))>0 or item.get('concept') or item.get('dream'):
            return 403,{'reason':'ITEM_NOT_TRADEABLE_IN_TRANSFER_LIST'}
        previous=owned_listing(s,item)
        if previous and previous['tradeState']=='active':
            return 200,{'id':previous['tradeId'],'tradeId':previous['tradeId'],'auctionInfo':[previous]}
        tid=number(state.get('owned_next_trade_id',800000000000))+1
        now=s.now_s();data=dict(tradeId=tid,itemId=iid,startingBid=start,buyNowPrice=buy_now,created=now,expiresAt=now+duration)
        item['itemState']='forSale'
        with state.conn:
            state.conn.execute('UPDATE items SET data=? WHERE id=?',(json.dumps(item),iid))
            for key,value in [('owned_next_trade_id',tid),('owned_auction_'+str(iid),data),('owned_auction_trade_'+str(tid),data)]:
                state.conn.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))
        row=owned_listing(s,item);s.PENDING_USERSESSION_REFRESH.set()
        return 200,{'id':tid,'tradeId':tid,'auctionInfo':[row]}


def dispatch(s,method,path,query,payload):
    search=criteria(query,payload)
    if path=='/ut/game/fifa21/auctionhouse' and method=='POST':return list_owned(s,payload)
    concept=path in ('/ut/game/fifa21/defid','/ut/game/fifa21/players','/ut/game/fifa21/players/search','/ut/game/fifa21/concept','/ut/game/fifa21/club/concept') or (
        path=='/ut/game/fifa21/club' and (str(value(search,'concept','dream','isconcept','concepts',default='')).lower() in ('true','1') or value(search,'type') in ('concept','conceptplayer')))
    if concept:
        if path=='/ut/game/fifa21/defid' and number(value(search,'defid')):
            rid=number(search.pop('defid'))
            search['maskeddefid']=number(s.PLAYER_DB.get(rid,{}).get('assetId'),rid)
        items=filter_items(catalogue(s,dict(search,type='player'),True),dict(search,type='player'))
        return 200,{'itemData':page(items,search),'players':page(items,search),'itemCount':len(items),'total':len(items)}
    if path=='/ut/game/fifa21/transfermarket' and method in ('GET','POST'):
        rows=catalogue(s,search)
        for item in rows:item['buyNowPrice']=local_price(item)
        rows=filter_items(rows,search)
        minimum=number(value(search,'micr','minbuy','minprice','minb'));maximum=number(value(search,'macr','maxbuy','maxprice','maxb'),1000000000)
        rows=[r for r in rows if minimum<=r['buyNowPrice']<=maximum]
        return 200,{'auctionInfo':[auction(s,x) for x in page(rows,search)],'credits':s.STATE.credits(),'total':len(rows),'count':len(page(rows,search))}
    if path in ('/ut/game/fifa21/search/filters','/ut/game/fifa21/filters'):
        def options(field,label):
            return [{'id':key,'name':name} for key,name in sorted({number(p.get(field)):str(p.get(label,p.get(field))) for p in s.PLAYER_DB.values()}.items())]
        return 200,{'leagues':options('leagueId','leagueName'),'nations':options('nation','nationName'),
                    'clubs':options('teamid','teamName'),'positions':sorted({p['preferredPosition'] for p in s.PLAYER_DB.values()}),
                    'rarities':[{'id':k,'name':v} for k,v in [(0,'Commun'),(1,'Rare'),(3,'TOTW'),(12,'Icône'),(21,'OTW')]]}
    match=re.fullmatch('/ut/game/fifa21/trade/(\d+)/(?:bid|offer)',path)
    if match and method in ('PUT','POST'):
        return buy(s,int(match.group(1)),number(value(search,'bid','buynowprice')))
    apply_match=re.fullmatch('/ut/game/fifa21/item/resource/(\d+)',path)
    if apply_match and method=='POST' and isinstance(payload,dict):
        targets=payload.get('apply',[])
        if isinstance(targets,dict):targets=[targets]
        if targets:
            first=targets[0]
            target=number(first.get('id',first.get('itemId'))) if isinstance(first,dict) else number(first)
            applied=apply_consumable(s,int(apply_match.group(1)),target)
            if applied is not None:return applied
    trade_match=re.fullmatch('/ut/game/fifa21/trade/(\d+)',path)
    if path in ('/ut/game/fifa21/trade/status','/ut/game/fifa21/trade/status/lite') or (trade_match and method=='GET'):
        requested=ids(value(search,'tradeids','tradeid')) if not trade_match else {int(trade_match.group(1))}
        rows=[]
        for tid in requested:
            own_data=s.STATE.get('owned_auction_trade_'+str(tid))
            if own_data:
                own_item=s.STATE.get_item(int(own_data['itemId']));own_row=owned_listing(s,own_item,own_data) if own_item else None
                if own_row:rows.append(own_row)
                continue
            receipt=s.STATE.get('market_receipt_'+str(tid))
            if receipt:rows.extend(receipt['auctionInfo']);continue
            rid=(tid-MARKET_BASE)%1000000000
            kind='player' if rid in s.PLAYER_DB else 'manager' if rid in s.MANAGER_DB else 'development' if any(x['resourceId']==rid for x in consumables(s)) else 'allclub'
            item=next((x for x in catalogue(s,{'type':kind}) if x['resourceId']==rid),None)
            if item:
                listing=auction(s,item)
                if listing['tradeId']==tid:rows.append(listing)
        return 200,{'auctionInfo':rows,'credits':s.STATE.credits()}
    if path in ('/ut/game/fifa21/watchlist','/ut/game/fifa21/watchlist/items'):
        watch=s.STATE.get('market_watchlist',[])
        if method in ('PUT','POST'):
            watch=list(set(watch)|ids(value(search,'tradeId','tradeIds')));s.STATE.set('market_watchlist',watch)
        if method=='DELETE':s.STATE.set('market_watchlist',[]);watch=[]
        rows=[auction(s,x) for x in catalogue(s,{'type':'all'})]
        return 200,{'auctionInfo':[x for x in rows if x['tradeId'] in watch],'credits':s.STATE.credits()}
    return None

def referenced_ids(squads):
    result=set()
    def scan(obj):
        if isinstance(obj,list):
            for x in obj:scan(x)
        elif isinstance(obj,dict):
            for key,val in obj.items():
                if key in ('itemId','id','captain') and isinstance(val,int):result.add(val)
                else:scan(val)
    scan(squads)
    return result

def deduplicate_owned(state):
    """Archive extras and redirect squad references; never discard the keeper."""
    if state.get('inventory_unique_v1'):return
    rows=state.conn.execute("SELECT id,resource_id,pile,data FROM items WHERE pile IN ('club','squad') ORDER BY id").fetchall()
    squads=state.list_squads();refs=referenced_ids(squads);groups={}
    for row in rows:
        item=json.loads(row['data'])
        if item.get('itemType')=='player':groups.setdefault(row['resource_id'],[]).append((row,item))
    replacements={};archived=[]
    for entries in groups.values():
        entries.sort(key=lambda pair:(pair[0]['id'] not in refs,-number(pair[1].get('contract')),pair[0]['id']))
        for row,item in entries[1:]:
            replacements[row['id']]=entries[0][0]['id'];archived.append(dict(row))
    backup_path=None
    if archived:
        state.conn.commit()
        folder=Path(state.path).parent/'backups';folder.mkdir(exist_ok=True)
        backup_path=folder/('before-inventory-unique-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
        with closing(sqlite3.connect(backup_path)) as backup:state.conn.backup(backup)
        def rewrite(obj):
            if isinstance(obj,list):return [rewrite(v) for v in obj]
            if isinstance(obj,dict):return {k:replacements.get(v,v) if k in ('itemId','id','captain') and isinstance(v,int) else rewrite(v) for k,v in obj.items()}
            return obj
        with state.conn:
            for row in archived:state.conn.execute('DELETE FROM items WHERE id=?',(row['id'],))
            for squad in squads:state.conn.execute('UPDATE squads SET data=? WHERE id=?',(json.dumps(rewrite(squad)),squad['id']))
            state.conn.execute('INSERT OR REPLACE INTO kv VALUES(?,?)',('inventory_duplicate_archive_v1',json.dumps(archived)))
    state.set('inventory_unique_v1',{'removed':len(archived),'backup':str(backup_path) if backup_path else None,'replacements':replacements})
