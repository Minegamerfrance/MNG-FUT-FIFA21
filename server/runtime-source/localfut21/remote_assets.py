"""Verified, lazy image downloads; one shared cache per Windows user."""
from pathlib import Path
import hashlib, json, os, threading, urllib.request

ROOT=Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/'asset-manifest.json').read_text(encoding='utf-8'))
CACHE=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'MNG21/asset-cache'
_lock=threading.Lock()

def _entry(path):
    try:key=Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:return None
    return MANIFEST['files'].get(key)

def has(path):
    return Path(path).is_file() or _entry(path) is not None

def read(path):
    path=Path(path)
    if path.is_file():return path.read_bytes()
    e=_entry(path)
    if not e:raise FileNotFoundError(path)
    sha=e['sha256'];target=CACHE/sha[:2]/(sha+Path(e['path']).suffix)
    def valid(data):return len(data)==e['size'] and hashlib.sha256(data).hexdigest()==sha
    with _lock:
        if target.is_file():
            data=target.read_bytes()
            if valid(data):return data
        url=MANIFEST['baseUrl'].rstrip('/')+'/'+e['path']
        if not url.startswith('https://raw.githubusercontent.com/Minegamerfrance/MNG-FUT-FIFA21/'):raise OSError('Invalid asset origin')
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'MNG-FUT-FIFA21'})
            with urllib.request.urlopen(req,timeout=15) as response:data=response.read(e['size']+1)
            if not valid(data):raise OSError('Image checksum mismatch: '+e['path'])
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_suffix(target.suffix+'.tmp');temporary.write_bytes(data);temporary.replace(target)
            return data
        except Exception as error:raise OSError('Image unavailable: '+e['path']) from error
