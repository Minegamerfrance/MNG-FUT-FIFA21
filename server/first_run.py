"""Read-only setup check and validated preferences for a new club."""
from pathlib import Path
import argparse,json,sqlite3,os,tempfile,unicodedata

def has_saved_club(runtime):
 db=runtime/'data/localfut15.sqlite3'
 if not db.is_file():return False
 with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
  tables={v[0] for v in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if 'kv' in tables and c.execute("SELECT 1 FROM kv WHERE key='credits'").fetchone():return True
  return 'items' in tables and c.execute('SELECT 1 FROM items LIMIT 1').fetchone() is not None

def ready(runtime,config):
 if has_saved_club(runtime):return True
 p=config/'config.json'
 if not p.is_file():return False
 d=json.loads(p.read_text(encoding='utf-8-sig'))
 return d.get('new_club_profile_version')==1 and bool(d.get('display_name','').strip())

def configure(runtime,config,nickname,club,abbr):
 if has_saved_club(runtime):raise ValueError('Ce profil possède déjà un club. Il reste inchangé.')
 nickname=nickname.strip();club=club.strip();abbr=abbr.strip().upper()
 for value,label,minimum,maximum in ((nickname,'pseudo',3,24),(club,'nom du club',3,24),(abbr,'abréviation',2,5)):
  if not minimum<=len(value)<=maximum or any(unicodedata.category(c).startswith('C') for c in value):raise ValueError('Vérifie le '+label+'.')
 if not abbr.isascii() or not abbr.isalnum():raise ValueError('Utilise 2 à 5 lettres ou chiffres pour l’abréviation.')
 path=config/'config.json';data=json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
 data.update(display_name=nickname,club_name=club,club_abbr=abbr,credits=10000,
   starter_credits=10000,starter_fifa_points=1000,initial_club_player_count=23,new_club_profile_version=1)
 config.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(dir=config,suffix='.tmp')
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def main():
 p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=Path,required=True);p.add_argument('--config-root',type=Path,required=True)
 p.add_argument('--nickname');p.add_argument('--club-name');p.add_argument('--abbr');a=p.parse_args()
 try:
  if a.nickname is not None:configure(a.runtime_root.resolve(),a.config_root.resolve(),a.nickname,a.club_name or '',a.abbr or '')
  print(json.dumps({'ready':ready(a.runtime_root.resolve(),a.config_root.resolve()),'existingClub':has_saved_club(a.runtime_root.resolve())}))
 except ValueError as e:print(json.dumps({'error':str(e)},ensure_ascii=True));raise SystemExit(2)

if __name__=='__main__':main()
