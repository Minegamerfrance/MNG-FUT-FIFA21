"""Publish only the public player catalogue and card art. Never reads club saves."""
from pathlib import Path
import argparse,base64,datetime,hashlib,io,json,os,sys,time,urllib.request,subprocess
from PIL import Image
REPOSITORY='Minegamerfrance/MNG-FUT-FIFA21'
FIELDS='name firstName lastName commonName rating preferredPosition preferredFoot workRateAttack workRateDefense weakFoot skillMoves dateOfBirth height weight leagueId leagueName teamid teamName nation nationName assetId resourceId rareflag rarityName special tier face attributes acquisition packEligible'.split()

def request(path,token,method='GET',value=None):
 data=json.dumps(value).encode() if value is not None else None
 req=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+path,data=data,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'MNG-FUT-catalogue'})
 with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)

def credential():
 p=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,check=True,timeout=45)
 values=dict(x.split('=',1) for x in p.stdout.splitlines() if '=' in x)
 if not values.get('password'):raise RuntimeError('Connexion GitHub indisponible')
 return values['password']

def prepare(core):
 players=json.loads((core/'players.json').read_text(encoding='utf-8-sig'))
 policy=json.loads((core/'catalog-policy.json').read_text(encoding='utf-8-sig'))
 # Mirror the enabled server catalogue; OTW and retired cards stay excluded.
 disabled=set(policy.get('disabledRarities',[]))
 manifest=json.loads((core/'asset-manifest.json').read_text(encoding='utf-8-sig'))
 cache=Path(os.environ['LOCALAPPDATA'])/'MNG21/asset-cache'
 assets={}
 def picture(rel):
  local=core/rel
  override=core/'web-card-art'/('rarity22.png' if '_22_' in rel and rel.startswith('custom-backgrounds/') else '_none')
  if override.is_file():raw=override.read_bytes()
  elif local.is_file():raw=local.read_bytes()
  elif (Path.home()/'Downloads/large'/Path(rel).name).is_file() and rel.startswith('custom-backgrounds/'):
   raw=(Path.home()/'Downloads/large'/Path(rel).name).read_bytes()
  elif rel in manifest['files']:
   e=manifest['files'][rel];stored=cache/e['sha256'][:2]/(e['sha256']+Path(e['path']).suffix)
   if stored.is_file():raw=stored.read_bytes()
   else:
    with urllib.request.urlopen(manifest['baseUrl']+'/'+e['path'],timeout=25) as r:raw=r.read()
   if hashlib.sha256(raw).hexdigest()!=e['sha256']:raise ValueError('Image invalide')
  else:return None
  img=Image.open(io.BytesIO(raw)).convert('RGBA');img.thumbnail((340,460))
  out=io.BytesIO();img.save(out,format='PNG',optimize=True);data=out.getvalue()
  name='web/assets/'+hashlib.sha256(data).hexdigest()[:24]+'.png';assets[name]=data;return name
 backgrounds={}
 for rarity in [3,12,22,37,63,85,98]:
  for quality in [1,0]:
   path=picture(f'custom-backgrounds/cards_bg_e_{quality}_{rarity}_0.dds')
   if path:backgrounds[str(rarity)]=path;break
 rows=[]
 for rid,m in players.items():
  if m.get('catalogEnabled') is False or int(m.get('rareflag',0)) in disabled:continue
  card={k:m[k] for k in FIELDS if k in m};card['resourceId']=int(rid)
  rel=f'custom-playerheads/p{rid}.dds';portrait=picture(rel)
  if not portrait and m.get('special'):
   portrait=picture(f"custom-playerheads/p{m.get('assetId',rid)}.dds")
  if portrait:card['portrait']=portrait
  rows.append(card)
 data=dict(schema=1,updatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),source='Catalogue MNG FUT FIFA 21',players=rows,backgrounds=backgrounds)
 return data,assets

def publish(core,status):
 data,assets=prepare(core)
 # Stable digest ignores the timestamp, avoiding commits when nothing changed.
 digest=hashlib.sha256(json.dumps([2,data['players'],data['backgrounds']],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 old=json.loads(status.read_text()) if status.exists() else {}
 if old.get('digest')==digest:return old
 data['digest']=digest
 token=credential();ref=request('/git/ref/heads/main',token);head=ref['object']['sha'];commit=request('/git/commits/'+head,token)
 tree=request('/git/trees/'+commit['tree']['sha']+'?recursive=1',token)
 existing={x['path']:x.get('sha') for x in tree['tree']}
 assets['web/catalog.json']=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
 assets['web/version.json']=json.dumps(dict(digest=digest,updatedAt=data['updatedAt'],players=len(data['players']))).encode()
 changes=[]
 for name,raw in assets.items():
  sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  if existing.get(name)==sha:continue
  blob=request('/git/blobs',token,'POST',{'content':base64.b64encode(raw).decode(),'encoding':'base64'})
  changes.append(dict(path=name,mode='100644',type='blob',sha=blob['sha']))
 if changes:
  nt=request('/git/trees',token,'POST',{'base_tree':commit['tree']['sha'],'tree':changes})
  nc=request('/git/commits',token,'POST',{'message':'Synchronize MNG FUT public player catalogue','tree':nt['sha'],'parents':[head]})
  request('/git/refs/heads/main',token,'PATCH',{'sha':nc['sha'],'force':False});head=nc['sha']
 record=dict(digest=digest,updatedAt=data['updatedAt'],players=len(data['players']),images=len(assets)-1,commit=head)
 status.parent.mkdir(parents=True,exist_ok=True);status.write_text(json.dumps(record,indent=2));return record

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path(__file__).parent/'runtime-source/localfut21');p.add_argument('--watch',action='store_true');p.add_argument('--export',type=Path);a=p.parse_args()
 state=Path(os.environ['LOCALAPPDATA'])/'MNG21/web-catalog';state.mkdir(parents=True,exist_ok=True)
 if a.export:
  data,assets=prepare(a.source);a.export.mkdir(parents=True,exist_ok=True);(a.export/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8');print(len(data['players']));return
 if a.watch:
  import msvcrt
  lock=(state/'watch.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:return
 while True:
  try:
   r=publish(a.source,state/'status.json');(state/'error.txt').unlink(missing_ok=True)
   if not a.watch:print(json.dumps(r))
  except Exception as e:
   # No request headers, credentials, or exception responses are persisted.
   (state/'error.txt').write_text(type(e).__name__+': '+str(e),encoding='utf8')
   if not a.watch:raise
  if not a.watch:break
  time.sleep(30)
if __name__=='__main__':main()
