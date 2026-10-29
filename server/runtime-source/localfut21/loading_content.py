import remote_assets
import event_schedule
from datetime import datetime,timezone
"""FUT loading carousel through the native dynamic-content provider."""
TRIGGER_ID='MNG_FUTLOAD'
CONTENT_PATH='/fut/loading/content'
ASSET_PATH='/fut/loading/rulebreakers-team1.jpg'
HUB_TRIGGER_ID='MNG_FUTHUB_RULEBREAKERS_2'
HUB_ASSET_PATH='/fut/loading/rulebreakers-panel-v3.png'
TEASER_PATH='/fut/loading/rulebreakers-team1-teaser.jpg'

def teaser(base):
    deadline=event_schedule.STARTS['rulebreakers']
    # FIFA21 FormatCountdown (RVA 0x4a31fe0) replaces this marker and
    # requires exactly YYYYMMDD-HHMMSS. ISO dates trigger the expired branch.
    return {'actionid':'220007','render':[
        {'name':'bodyImage','type':'IMAGE','value':base+TEASER_PATH,
         'attributes':{'x':'160','y':'90','width':'1600','height':'900'}},
        {'name':'releaseDate','type':'TEXT','value':'RULEBREAKERS — VENDREDI 6 NOVEMBRE À 20 H (PARIS)',
         'attributes':{'x':'400','y':'866','width':'1120','height':'42','alignment':'1','size':'26','colour':'4294967295','highlightColour':'4294967295'}},
        {'name':'bodyText','type':'TEXT','value':'^COUNTDOWNTO^',
         'attributes':{'x':'400','y':'910','width':'1120','height':'64','alignment':'1','size':'44','colour':'4294967295','highlightColour':'4294967295',
                       'countdownTime':datetime.fromtimestamp(deadline,timezone.utc).strftime('%Y%m%d-%H%M%S')}}],
        'attributes':{'displayTime':'5','doNotDisplay':'0'}}

def settings(base):
    entries=list({
        'DYNAMICCONTENT_ACTIVE':'1',
        'DYNAMICCONTENT_TRIGGERDATA':'12|'+TRIGGER_ID+'|0|1|2,2|'+HUB_TRIGGER_ID+'|0|1|5',
        'DYNAMICCONTENT_ARUBA_MESSAGEURL':base+CONTENT_PATH,
        'ONLINE/DYNAMIC_CONTENT_ENABLED':'1',
        'DYNAMICCONTENT_MAX_IMAGE_PER_MESSAGE':'1',
        'DYNAMICCONTENT_MAX_TEXTBOX_PER_MESSAGE':'2',
    }.items())
    for row in dict(entries)['DYNAMICCONTENT_TRIGGERDATA'].split(','):
        assert int(row.split('|')[4])>0, 'Dynamic content count must be positive'
    return entries

def content(base,trigger_ids=None):
    triggers=[{'triggerid':TRIGGER_ID,'actions':[{
        'actionid':'220001','render':[{'name':'bodyImage','type':'IMAGE',
        'value':base+ASSET_PATH,'attributes':{
            'x':'160','y':'90','width':'1600','height':'900'}}],
        'attributes':{'displayTime':'5','doNotDisplay':'0'}}]},
        {'triggerid':HUB_TRIGGER_ID,'actions':[{
            'actionid':'240005','render':[{'name':'bodyImage','type':'IMAGE',
                'value':base+HUB_ASSET_PATH,'attributes':{'x':'0','y':'0','width':'379','height':'576'}}],
            'attributes':{'displayTime':'10','doNotDisplay':'0'}}]}]
    for trigger in triggers:
        loading=trigger['triggerid']==TRIGGER_ID
        trigger['actions'].append({'actionid':'230001' if loading else '240002',
            'render':[{'name':'bodyImage','type':'IMAGE','value':base+('/fut/loading/totw1-new.png' if loading else '/fut/loading/totw1-panel-v1.png'),
                'attributes':{'x':'160','y':'90','width':'1600','height':'900'} if loading else
                {'x':'0','y':'0','width':'379','height':'576'}}],
            'attributes':{'displayTime':'5' if loading else '10','doNotDisplay':'0'}})
    for trigger in triggers:
        trigger['actions']=[a for a in trigger['actions'] if event_schedule.active('rulebreakers' if a['actionid'] in ('220001','240005') else 'totw1')]
        if trigger['triggerid']==TRIGGER_ID and not event_schedule.active('rulebreakers'):
            trigger['actions'].insert(0,teaser(base))
    triggers=[t for t in triggers if t['actions']]
    if trigger_ids:
        requested={trigger_ids} if isinstance(trigger_ids,str) else set(trigger_ids)
        triggers=[t for t in triggers if t['triggerid'] in requested]
    return {'triggers':triggers}

def route(s,method,path,payload):
    headers={'Cache-Control':'no-store','Content-Type':'application/json'}
    if path==TEASER_PATH and method in ('GET','HEAD'):
        if event_schedule.active('rulebreakers'):
            return 404,headers,s.json_bytes({'reason':'teaserEnded'})
        return 200,{'Content-Type':'image/jpeg','Cache-Control':'no-store'},remote_assets.read(s.ROOT/'assets/livemessaging/rulebreakers-team1-teaser.jpg') if method=='GET' else b''
    if path==CONTENT_PATH and method in ('GET','POST'):
        ids=[]
        if method=='POST':
            ids=payload.get('triggerids',[]) if isinstance(payload,dict) else None
            if not isinstance(ids,(list,str)) or isinstance(ids,list) and any(not isinstance(x,str) for x in ids):
                return 400,headers,s.json_bytes({'triggers':[]})
        s.log.info('FIFA21 dynamic content requested triggers=%s',ids)
        return 200,headers,s.json_bytes(content(f"http://127.0.0.1:{s.CFG['fut_port']}",ids))
    if path in ('/fut/loading/totw1-panel-v1.png','/fut/loading/rulebreakers-panel-v3.png') and method in ('GET','HEAD'):
        asset=s.ROOT/'assets/livemessaging'/path.rsplit('/',1)[1]
        return 200,{'Content-Type':'image/png','Cache-Control':'no-store'},remote_assets.read(asset) if method=='GET' else b''
    if path=='/fut/loading/totw1-new.png'  and method in ('GET','HEAD'):
        asset=s.ROOT/'assets/livemessaging/totw1-new.png'
        return 200,{'Content-Type':'image/png','Cache-Control':'no-store'},remote_assets.read(asset) if method=='GET' else b''
    if path.startswith('/fut/loading/'):

        if path not in (ASSET_PATH,HUB_ASSET_PATH) or method not in ('GET','HEAD'):
            return 404,headers,s.json_bytes({'reason':'unknownLoadingAsset'})
        asset=s.ROOT/'assets/livemessaging'/('rulebreakers-panel-v3.png' if path==HUB_ASSET_PATH else 'rulebreakers-team1.jpg')
        if not remote_assets.has(asset):
            return 404,headers,s.json_bytes({'reason':'missingLoadingAsset'})
        s.log.info('FIFA21 Rulebreakers image requested path=%s',path)
        return 200,{'Content-Type':'image/png' if path==HUB_ASSET_PATH else 'image/jpeg','Cache-Control':'no-store'},remote_assets.read(asset) if method=='GET' else b''
    return None
