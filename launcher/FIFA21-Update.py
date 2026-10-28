"""Signed FIFA 21 distribution updater. Never writes saved clubs or user settings."""
from pathlib import Path, PurePosixPath
import argparse, base64, hashlib, io, json, os, shutil, tempfile, urllib.request, zipfile
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec

MANIFEST_URL='https://raw.githubusercontent.com/Minegamerfrance/MNG-FUT-FIFA21/main/updates/server.json'
PUBLIC_KEY_PEM='-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEi8rbVBfmd4PKKgMXy5dSrsAY7gYT\n/4+4GP7pFNWWlHNcnqfRIVtIGTBIaO2BgSLwLxuxHvjpe6NccS+Z09mJwg==\n-----END PUBLIC KEY-----\n'

def get(url):
    if not url.startswith(('https://raw.githubusercontent.com/Minegamerfrance/MNG-FUT-FIFA21/','https://github.com/Minegamerfrance/MNG-FUT-FIFA21/releases/download/')):
        raise ValueError('Unexpected update origin')
    req=urllib.request.Request(url,headers={'User-Agent':'MNG-FUT-FIFA21-Updater','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=90) as response:return response.read()

def manifest():
    raw=get(MANIFEST_URL);sig=base64.b64decode(get(MANIFEST_URL+'.sig'),validate=True)
    key=serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())
    key.verify(sig,raw,ec.ECDSA(hashes.SHA256()))
    m=json.loads(raw)
    if m.get('gameId')!='21' or not isinstance(m.get('files'),dict):raise ValueError('Invalid FIFA 21 manifest')
    return m

def safe_name(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:raise ValueError('Unsafe archive path')
    if not p.parts or p.parts[0] in ('runtime','backups','data','certs','.git'):raise ValueError('User state cannot be replaced')
    if any(x in ('certs','__pycache__') for x in p.parts) or p.suffix in ('.key','.pem','.pfx','.sqlite3','.log'):raise ValueError('Non-distributable path')
    return p

def install(target,m,download=None):
    # Refuse a program update while this exact server is answering on its local port.
    try:
        req=urllib.request.Request('http://127.0.0.1:8090/localfut/auth/bootstrap')
        with urllib.request.urlopen(req,timeout=1) as response:running=json.load(response)
    except Exception:running=None
    if running and running.get('version')==1:raise RuntimeError('ArrÃªtez le serveur FIFA 21 depuis le lanceur avant la mise Ã  jour.')
    raw=(download or get)(m['source'])
    if len(raw)!=m['size'] or hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('Package checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=[info.filename for info in archive.infolist() if not info.is_dir()]
        if len(names)!=len(set(names)) or set(names)!=set(m['files']):raise ValueError('Package file list mismatch')
        for name in names:
            safe_name(name);data=archive.read(name)
            if hashlib.sha256(data).hexdigest()!=m['files'][name]:raise ValueError('File checksum mismatch: '+name)
        with tempfile.TemporaryDirectory(prefix='MNG21-update-') as tmp:
            stage=Path(tmp)
            for name in names:
                dest=stage.joinpath(*safe_name(name).parts);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(archive.read(name))
            # Only listed program files are replaced; unrelated files remain untouched.
            saved=[]
            try:
                for name in names:
                    dest=target.joinpath(*safe_name(name).parts)
                    previous=dest.read_bytes() if dest.is_file() else None
                    saved.append((dest,previous));dest.parent.mkdir(parents=True,exist_ok=True)
                    pending=dest.with_name(dest.name+'.mng-update');pending.write_bytes((stage/name).read_bytes());os.replace(pending,dest)
                stamp=target/'mng21-version.json';stamp.write_text(json.dumps({'version':m['version'],'gameId':'21'}),encoding='utf-8')
            except Exception:
                for dest,previous in reversed(saved):
                    if previous is None:dest.unlink(missing_ok=True)
                    else:dest.write_bytes(previous)
                raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);p.add_argument('--check',action='store_true');p.add_argument('--force',action='store_true');a=p.parse_args()
    m=manifest();stamp=a.target/'mng21-version.json';installed=json.loads(stamp.read_text()).get('version','0.0.0') if stamp.is_file() else '0.0.0'
    changed=installed!=m['version']
    if not a.check and (changed or a.force):install(a.target,m)
    print(json.dumps({'version':m['version'],'installedVersion':installed if a.check else m['version'],'updateAvailable':changed,'installed':not a.check}))

if __name__=='__main__':main()
