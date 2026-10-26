import remote_assets
"""Native FUT entrance announcements, matching the installed FIFA 20 flow."""
import json

KEY='mng_fut21_announcements_read_v1'
HUB_KEY='mng_fifa21_user_hub_client_data'


def event(s):
    path=s.ROOT/'live-event.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def hub_data(s):
    return s.STATE.get(HUB_KEY,{'entries':[{'key':0,'value':13},{'key':1,'value':12}]})


def messages(s):
    e=event(s)
    if not e or e.get('placement') == 'loading' or int(e['id']) in s.STATE.get(KEY,[]):
        return []
    name=e['poster']
    if name != s.Path(name).name:
        return []
    return [dict(messageId=int(e['id']),messageType=1,seriousType=0,displayTime=1,
        priority=0,renders=[dict(name='bodyImage',type='IMAGE',
            value=f"http://127.0.0.1:{s.CFG['fut_port']}/fut/livemessaging/{name}",attributes={})])]


def route(s,method,path,query,payload):
    headers={'Cache-Control':'no-store'}
    if method=='GET' and path.startswith('/fut/livemessaging/'):
        e=event(s)
        if not e or path != '/fut/livemessaging/'+e['poster']:
            return 404,headers,s.json_bytes({'reason':'unknownPoster'})
        poster=s.ROOT/'assets/livemessaging'/e['poster']
        if not remote_assets.has(poster):
            return 404,headers,s.json_bytes({'reason':'missingPoster'})
        return 200,dict(headers,**{'Content-Type':'image/jpeg'}),remote_assets.read(poster)
    if path=='/ut/game/fifa21/clientdata/userhubdata':
        if method in ('POST','PUT'):
            entries=payload.get('entries') if isinstance(payload,dict) else None
            if not isinstance(entries,list) or any(not isinstance(x,dict) or
                type(x.get('key')) is not int or type(x.get('value')) is not int or
                not 0<=x['key']<=65535 or not 0<=x['value']<=0xffffffff for x in entries):
                return 400,headers,s.json_bytes({'reason':'invalidHubClientData'})
            values={x['key']:x['value'] for x in hub_data(s)['entries']}
            intro_seen=values.get(1,0)&1024
            values.update({x['key']:x['value'] for x in entries})
            if intro_seen:values[1]=values.get(1,0)|1024
            s.STATE.set(HUB_KEY,{'entries':[dict(key=k,value=v) for k,v in sorted(values.items())]})
        return 200,headers,s.json_bytes(hub_data(s))
    if path=='/ut/game/fifa21/livemessage' and method in ('POST','PUT'):
        ids=payload.get('idList') if isinstance(payload,dict) else None
        e=event(s)
        if not isinstance(ids,list) or any(type(i) is not int or not e or i!=int(e['id']) for i in ids):
            return 400,headers,s.json_bytes({'reason':'invalidLiveMessages'})
        with s.STATE.lock:s.STATE.set(KEY,sorted(set(s.STATE.get(KEY,[]))|set(ids)))
        return 200,headers,s.json_bytes({'success':True})
    if method=='GET' and path in ('/ut/game/fifa21/livemessage/template','/ut/game/fifa21/template') and query.get('screen',[''])[0].lower()=='futlivemsggen4':
        entries=messages(s)
        return 200,headers,s.json_bytes(dict(messageList=entries,messagesAvailable=len(entries),messagesRead=0))
    return None
