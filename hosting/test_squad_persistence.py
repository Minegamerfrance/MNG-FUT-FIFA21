"""Exercise the production squad persistence methods without importing game services."""
import ast,json,sqlite3,threading,tempfile,unittest
from pathlib import Path
source=Path(__file__).resolve().parents[1]/'server/runtime-source/localfut21/server.py'
tree=ast.parse(source.read_text(encoding='utf-8-sig'))
state=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='State')
methods=[n for n in state.body if isinstance(n,ast.FunctionDef) and n.name in ('save_squad','_save_squad_locked')]
namespace={'Any':object,'json':json}
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='SquadStore',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])),str(source),'exec'),namespace)
class Persistence(unittest.TestCase):
 def test_partial_save_and_reconnect(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'club.sqlite3'; obj=namespace['SquadStore'](); obj.lock=threading.RLock(); obj.conn=sqlite3.connect(db)
   obj.conn.execute('CREATE TABLE squads(id INTEGER PRIMARY KEY,name TEXT,active INTEGER,data TEXT)')
   obj.list_items=lambda:[]; obj.get_item=lambda i:None
   players=[{'index':i,'itemId':100+i} for i in range(23)]
   obj.save_squad({'id':1,'name':'My XI','formation':'f433','players':players,'active':True})
   obj.save_squad({'id':1,'captain':100,'kicktakers':[{'id':101}]})
   obj.save_squad({'id':1,'formation':'f442'})
   obj.conn.close(); obj.conn=sqlite3.connect(db)
   saved=json.loads(obj.conn.execute('SELECT data FROM squads WHERE id=1').fetchone()[0])
   self.assertEqual(saved['players'],players); self.assertEqual(saved['name'],'My XI'); self.assertEqual(saved['captain'],100); self.assertEqual(saved['formation'],'f442')
   obj.save_squad({'id':2,'players':[{'index':0,'itemId':999}]})
   obj.save_squad({'id':1,'players':[]})
   self.assertEqual(json.loads(obj.conn.execute('SELECT data FROM squads WHERE id=1').fetchone()[0])['players'],[])
   self.assertEqual(json.loads(obj.conn.execute('SELECT data FROM squads WHERE id=2').fetchone()[0])['players'][0]['itemId'],999)
   obj.conn.close()
if __name__=='__main__':unittest.main()
