"""Native FIFA21 FUT roster delivery, versioned from the loaded server catalogue."""
import copy,hashlib,json,struct,threading,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
from squad_payload import read_database,build_database,database_crc,compress,decompress
POSITIONS={'GK':0,'RWB':2,'RB':3,'CB':5,'LB':7,'LWB':8,'CDM':10,'CM':14,'RM':12,'LM':16,'CAM':18,'CF':21,'RW':23,'ST':25,'LW':27}
_lock=threading.RLock()
def _columns(t):return {n.decode():(kind,offset,depth) for kind,offset,n,depth in struct.iter_unpack('<II4sI',t['fields'])}
def _number(row,f):kind,offset,depth=f;assert kind==3;return int.from_bytes(row,'little')>>offset&((1<<depth)-1)
def _set(row,f,value):
 kind,offset,depth=f
 if kind!=3 or type(value)!=int or not 0<=value<1<<depth:raise ValueError('Native field out of range')
 mask=((1<<depth)-1)<<offset;return ((int.from_bytes(row,'little')&~mask)|(value<<offset)).to_bytes(len(row),'little')
def _base_cards(s):
 # One native search identity per asset; promotional editions retain their own item stats.
 return {int(rid):m for rid,m in s.PLAYER_DB.items() if int(rid)==int(m.get('assetId',rid)) and int(m.get('rareflag',0)) in (0,1)}
def build(s,definitions,source,version):
 tables=read_database(source);players=next(t for t in tables if t['shortname']=='CZUM');cols=_columns(players);info=definitions['fields'];cards=_base_cards(s);rows=[];changed=[];found=set()
 for pos in range(0,len(players['records']),players['record_size']):
  row=players['records'][pos:pos+players['record_size']];rid=_number(row,cols[info['playerid']['short']]);card=cards.get(rid);updated=row
  if card:
   found.add(rid);values=dict(overallrating=int(card['rating']),preferredposition1=POSITIONS[card['preferredPosition']],weakfootabilitytypecode=int(card.get('weakFoot',3)),skillmoves=int(card.get('skillMoves',1))-1)
   values.update({k.lower():int(v) for k,v in card.get('attributes',{}).items() if k!='gkSpeed' and int(v)>0})
   for key,value in values.items():
    f=info.get(key)
    if f is None or f['short'] not in cols:continue
    if key in ('height','weight') and value==0:continue
    try:updated=_set(updated,cols[f['short']],value-f['minimum'])
    except ValueError as error:raise ValueError(f'{rid} {key} value={value} field={cols[f["short"]]} minimum={f["minimum"]}') from error
   if updated!=row:changed.append(rid)
  rows.append(updated)
 players['records']=b''.join(rows)
 v=next(t for t in tables if t['shortname']=='DbIl');record=bytearray(v['records']);assert record[4:44].decode()==definitions['schema'];struct.pack_into('<H',record,2,version-1);record[44]|=1;v['records']=bytes(record)
 database=build_database(tables);payload=compress(database);assert decompress(payload)==database
 crc=database_crc(tables)
 return payload,dict(schemaCRC=definitions['schema'],advertisedSchemas=definitions.get('advertisedSchemas',[definitions['schema']]),version=version,databaseCRC=crc if crc<0x80000000 else crc-0x100000000,size=len(payload),sha256=hashlib.sha256(payload).hexdigest(),tables=len(tables),playersChanged=len(changed),changedPlayerIds=changed,baseCardsMatched=len(found),missingBaseIds=sorted(cards.keys()-found))
def ensure(s):
 with _lock:
  definitions=json.loads((s.ROOT/'roster-baseline/metadata.json').read_text(encoding='utf8'));fingerprint=hashlib.sha256(json.dumps(dict(cards=_base_cards(s),baseline=[d['baselineSha256'] for d in definitions],generator=4),sort_keys=True,separators=(',',':')).encode()).hexdigest()
  directory=s.RUNTIME_ROOT/'roster-updates';directory.mkdir(parents=True,exist_ok=True);index=directory/'current.json'
  try:current=json.loads(index.read_text(encoding='utf8'))
  except (OSError,ValueError):current={}
  if current.get('fingerprint')==fingerprint and all((directory/u['file']).is_file() and hashlib.sha256((directory/u['file']).read_bytes()).hexdigest()==u['sha256'] for u in current.get('updates',[])) and len(current.get('updates',[]))==len(definitions):return current
  version=max(21001,int(current.get('version',21000))+1)
  if version>65535:raise ValueError('Native roster version exhausted')
  updates=[]
  for d in definitions:
   source=(s.ROOT/'roster-baseline'/(d['label']+'.db')).read_bytes();assert hashlib.sha256(source).hexdigest()==d['baselineSha256'];payload,meta=build(s,d,source,version);meta['file']=f'mng21-{d["label"]}-{version}-{fingerprint[:12]}.bin';target=directory/meta['file'];temp=target.with_suffix('.tmp');temp.write_bytes(payload);temp.replace(target);updates.append(meta)
  current=dict(version=version,fingerprint=fingerprint,updates=updates);temp=index.with_suffix('.tmp');temp.write_text(json.dumps(current,indent=2),encoding='utf8');temp.replace(index)
  s.log.info('FIFA21 ROSTER generated version=%s corrected=%s',version,[u['playersChanged'] for u in updates]);return current
def manifest(s,original):
 current=ensure(s);root=ET.fromstring(original);group=root.find('squadInfoSet');template=next(t for t in group.findall('squadInfo') if t.get('platform')=='pc64')
 for u in current['updates']:
  # Selection uses the schema from before FUT swaps in cards_ng_db.
  # Both accepted manifest identities therefore point to the same real FUT savegroup.
  for selection_schema in u.get('advertisedSchemas',[u['schemaCRC']]):
   squad=copy.deepcopy(template)
   for key,value in dict(dbSchemaCRC=selection_schema,dbFUTVer=current['version'],dbFUTCRC=u['databaseCRC'],dbFUTLoc='fifa/fifalive/squads/'+u['file']).items():squad.find(key).text=str(value)
   group.append(squad)
 return ET.tostring(root,encoding='utf8',xml_declaration=True)
def response(s,method,path):
 # Native FIFA21 removes the leading fifa/ and resolves against CONTENT_URL.
 prefixes=('/fifa/fifalive/squads/','/contentfifa/fifalive/squads/','/content/fifa/fifalive/squads/','/fifalive/squads/')
 prefix=next((x for x in prefixes if path.startswith(x)),None)
 if prefix is None:return None
 if method not in ('GET','HEAD'):return 405,{'Allow':'GET, HEAD'},b''
 name=path[len(prefix):]
 # Published old versions remain fetchable if the server regenerated after a manifest was served.
 if not name.startswith('mng21-') or '/' in name or '\\' in name or not name.endswith('.bin'):return 404,{},b''
 p=s.RUNTIME_ROOT/'roster-updates'/name
 if not p.is_file():return 404,{},b''
 data=p.read_bytes();s.log.info('FIFA21 ROSTER download served file=%s bytes=%s; client application pending',name,len(data))
 return 200,{'Content-Type':'application/octet-stream','Content-Length':str(len(data)),'Cache-Control':'no-store'},data if method=='GET' else b''
def apply(s):
 if getattr(s,'_roster_sync_applied',False):return
 ensure(s);original_get=s.EaswHandler.do_GET;original_route=s.route_fut;original_config=s._blaze_osdk_core_config
 def config():
  entries=original_config();base=dict(entries)['ROSTERUPDATE_URL'].rsplit('/',1)[0];settings={'FUT_SQUAD_UPDATE':'1','FUT/ROSTERUPDATE_URL':base+'/roster','ROSTER_URL':base+'/roster','LIVE_CONTENT_HOST':base}
  return [(k,v) for k,v in entries if k not in settings]+list(settings.items())
 def get(handler):
  path=urllib.parse.urlsplit(handler.path).path
  if path=='/roster':
   try:body=manifest(s,handler.ROSTER_XML)
   except Exception:s.log.exception('Native roster generation failed; retaining normal FUT entry');return original_get(handler)
   s.log.info('FIFA21 ROSTER manifest advertised version=%s',ensure(s)['version']);handler._send(200,body,'text/xml',{'Cache-Control':'no-store',**handler.EASW_HEADERS});return
  result=response(s,'GET',path)
  if result is not None:
   code,headers,body=result;handler._send(code,body,headers.pop('Content-Type','application/octet-stream'),headers);return
  return original_get(handler)
 def route(method,path,headers,body):
  result=response(s,method,urllib.parse.urlsplit(path).path)
  return result if result is not None else original_route(method,path,headers,body)
 s.EaswHandler.do_GET=get;s.route_fut=route;s._blaze_osdk_core_config=config;s._roster_sync_applied=True
