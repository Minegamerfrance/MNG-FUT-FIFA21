"""One-off, backed-up withdrawal. Run only while all club workers are stopped."""
import argparse,json,sqlite3,uuid
from pathlib import Path

def withdraw(path,backups,apply=False):
    con=sqlite3.connect(path)
    try:
        rows=con.execute('SELECT id,resource_id,data FROM items').fetchall()
        removed={iid for iid,rid,raw in rows if (item:=json.loads(raw)).get('itemType','player')=='player' and int(item.get('rareflag',0)) in (3,22)}
        result=dict(club=path.parents[2].name,cards=len(removed),applied=False)
        if not apply or not removed:return result
        backups.mkdir(parents=True,exist_ok=True,mode=0o700)
        backup=backups/(result['club']+'-'+uuid.uuid4().hex+'.sqlite3')
        target=sqlite3.connect(backup)
        try:
            con.backup(target)
            assert target.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        finally:target.close()
        def linked(slot):
            if not isinstance(slot,dict):return slot in removed if isinstance(slot,int) else False
            return any(slot.get(k) in removed for k in ('itemId','id') if isinstance(slot.get(k),int)) or (isinstance(slot.get('itemData'),dict) and slot['itemData'].get('id') in removed)
        def repair(value):
            if isinstance(value,list):return [repair(v) for v in value if not linked(v)]
            if isinstance(value,dict):
                return {k:(0 if k in ('captain','itemId','id') and isinstance(v,int) and v in removed else repair(v)) for k,v in value.items()}
            return value
        with con:
            for iid in removed:con.execute('DELETE FROM items WHERE id=?',(iid,))
            for sid,raw in con.execute('SELECT id,data FROM squads').fetchall():
                value=json.loads(raw);updated=repair(value)
                if updated!=value:con.execute('UPDATE squads SET data=? WHERE id=?',(json.dumps(updated),sid))
            for key,raw in con.execute("SELECT key,value FROM kv WHERE key LIKE '%squad_%' OR key LIKE 'owned_auction_%' OR key LIKE 'player_pick:%'").fetchall():
                value=json.loads(raw)
                if key.startswith('owned_auction_') and isinstance(value,dict) and linked(value):
                    con.execute('DELETE FROM kv WHERE key=?',(key,));continue
                updated=repair(value)
                if key.startswith('player_pick:') and isinstance(updated,dict) and any(int(c.get('rareflag',0)) in (3,22) for c in updated.get('choices',[]) if isinstance(c,dict)):
                    updated['choices']=[]
                if updated!=value:con.execute('UPDATE kv SET value=? WHERE key=?',(json.dumps(updated),key))
        assert con.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        assert {r[0] for r in con.execute('SELECT id FROM items')}=={r[0] for r in rows}-removed
        result.update(applied=True,backup=str(backup))
        return result
    finally:con.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--club-root',type=Path,required=True)
    parser.add_argument('--backup-root',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    for path in sorted(args.club_root.glob('*/runtime/data/localfut15.sqlite3')):
        print(json.dumps(withdraw(path,args.backup_root,args.apply)))
