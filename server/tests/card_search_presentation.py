"""Native search identities and custom card presentation regression."""
import json,os,sys,tempfile,struct,xml.etree.ElementTree as ET
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'runtime-source/localfut21'
os.environ['LOCALFUT_RUNTIME_ROOT']=tempfile.mkdtemp(prefix='mng-card-search-')
os.environ['LOCALFUT21_USER_CONFIG_ROOT']=tempfile.mkdtemp(prefix='mng-card-config-')
sys.path.insert(0,str(p))
import server as s
import roster_update as r
cards=r._base_cards(s)
assert cards[189596]['rating']==88
assert cards[189509]['rating']==88 and cards[189509]['name']=='Thiago'
assert cards[182521]['rating']==88
assert 67291385 not in cards
current=r.ensure(s)
assert current['version']>21005, 'Fresh VPS clubs must update clients retaining the local 21005 roster'
assert r.ensure(s)==current, 'An unchanged roster must not trigger another update'
manifest=ET.fromstring(r.manifest(s,s.EaswHandler.ROSTER_XML))
for update in current['updates']:
 for schema in update['advertisedSchemas']:
  entries=[x for x in manifest.findall('./squadInfoSet/squadInfo') if x.findtext('dbSchemaCRC')==schema]
  assert len(entries)==1
  entry=entries[0]
  assert int(entry.findtext('dbFUTVer'))==current['version']
  code,headers,payload=r.response(s,'GET','/contentfifa/fifalive/squads/'+update['file'])
  assert code==200 and payload==(s.RUNTIME_ROOT/'roster-updates'/update['file']).read_bytes()
  version_table=next(t for t in r.read_database(r.decompress(payload)) if t['shortname']=='DbIl')
  assert struct.unpack_from('<H',version_table['records'],2)[0]+1==current['version']
for spec,u in zip(json.loads((p/'roster-baseline/metadata.json').read_text()),current['updates']):
 tables=r.read_database(r.decompress((s.RUNTIME_ROOT/'roster-updates'/u['file']).read_bytes()))
 t=next(t for t in tables if t['shortname']=='CZUM');cols=r._columns(t);fields=spec['fields'];ratings={}
 for offset in range(0,len(t['records']),t['record_size']):
  row=t['records'][offset:offset+t['record_size']]
  asset=r._number(row,cols[fields['playerid']['short']])
  if asset in (189596,189509):ratings[asset]=r._number(row,cols[fields['overallrating']['short']])+fields['overallrating']['minimum']
 assert ratings=={189596:88,189509:88},ratings
style=json.loads((p/'custom-backgrounds/rarity19.json').read_text())
assert style['colorArray']==[0,0xffffff]
for field in ('expColorIndices','smallColorIndices','collColorIndices'):
 assert style[field][:5]==[1,2,2,2,2] and style[field][5:]==[0,0,0,0]
print('PASS: Muller and Thiago native search ratings 88, regular Kroos 88 retained, MNG lower text white and decoration tint overrides cleared')

# Account indexes can lag behind a player's retained FIFA save, or be ahead
# after a later catalogue revision. Never roll either deployment backwards.
original_root=s.RUNTIME_ROOT
try:
 for previous in (21002,21005,current['version']+2):
  s.RUNTIME_ROOT=Path(tempfile.mkdtemp(prefix='mng-roster-migration-'))
  directory=s.RUNTIME_ROOT/'roster-updates';directory.mkdir()
  (directory/'current.json').write_text(json.dumps(dict(version=previous)))
  updated=r.ensure(s)
  assert updated['version']==max(r.MIN_ROSTER_VERSION,previous+1)
  assert r.ensure(s)==updated
finally:s.RUNTIME_ROOT=original_root
print('PASS: fresh and migrated VPS clubs advertise a roster newer than retained 21005; manifest/download/header versions agree; newer indexes stay monotonic')
