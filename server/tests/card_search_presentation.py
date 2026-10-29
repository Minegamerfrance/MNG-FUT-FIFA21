"""Native search identities and custom card presentation regression."""
import json,os,sys,tempfile
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
 assert style[field][:5]==[1,1,2,2,2] and style[field][5:]==[0,0,0,0]
print('PASS: Muller and Thiago native search ratings 88, regular Kroos 88 retained, MNG lower text white and decoration tint overrides cleared')
