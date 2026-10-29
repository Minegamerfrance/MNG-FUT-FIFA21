import ast,json,re,sqlite3,threading,tempfile,unittest
from pathlib import Path
from test_squad_persistence import namespace,source
class Selector(unittest.TestCase):
 def test_create_select_rename_delete_and_restart(self):
  tree=ast.parse(source.read_text(encoding='utf-8-sig'))
  route=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_route_fut')
  branches=[]
  for n in route.body:
   text=ast.unparse(n)
   if isinstance(n,ast.If) and isinstance(n.test,(ast.Compare,ast.BoolOp)) and any(isinstance(v,ast.Constant) and v.value in ("/ut/game/fifa21/squad/list","/ut/game/fifa21/squad","/ut/game/fifa21/squad/active") for v in ast.walk(n.test)):branches.append(n)
   if isinstance(n,ast.Assign) and 'regular_squad = re.fullmatch' in text:branches.append(n)
   if isinstance(n,ast.If) and text.startswith('if regular_squad'):branches.append(n)
  self.assertEqual(len(branches),6)
  code=ast.parse('def dispatch(method, low, payload):\n pass').body[0];code.body=branches
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'club.sqlite3';obj=namespace['SquadStore']();obj.lock=threading.RLock();obj.conn=sqlite3.connect(db)
   obj.conn.execute('CREATE TABLE squads(id INTEGER PRIMARY KEY,name TEXT,active INTEGER,data TEXT)')
   obj.list_items=lambda:[];obj.get_item=lambda i:None;obj.get=lambda key,default=None:default;obj._squad_item_ids=lambda squad:[]
   obj.list_squads=lambda:[json.loads(r[0]) for r in obj.conn.execute('SELECT data FROM squads ORDER BY active DESC,id')]
   obj.delete_squad=lambda sid:obj.conn.execute('DELETE FROM squads WHERE id=?',(sid,))
   native=lambda sid=None:next(s for s in obj.list_squads() if sid is None or s['id']==sid)
   scope={'STATE':obj,'json_bytes':lambda x:json.dumps(x).encode(),'_native_squad':native,'re':re}
   exec(compile(ast.fix_missing_locations(ast.Module(body=[code],type_ignores=[])),str(source),'exec'),scope)
   call=lambda m,p,b={}:json.loads(scope['dispatch'](m,p,b)[2])
   obj.save_squad({'id':1,'squadName':'Original','players':[{'index':0,'itemId':100}],'active':True})
   created=call('POST','/ut/game/fifa21/squad',{'squadName':'Second'})
   self.assertEqual(created['id'],2);self.assertEqual(obj.list_squads()[0]['id'],1)
   self.assertEqual(len(call('GET','/ut/game/fifa21/squad/list')['squad']),2)
   call('PUT','/ut/game/fifa21/squad/active',{'squadId':2})
   call('PUT','/ut/game/fifa21/squad/2',{'squadName':'Renamed','players':[{'index':1,'itemId':101}]})
   obj.conn.close();obj.conn=sqlite3.connect(db)
   self.assertEqual(call('GET','/ut/game/fifa21/squad/active')['squadName'],'Renamed')
   self.assertEqual(call('GET','/ut/game/fifa21/squad/1')['players'][0]['itemId'],100)
   call('DELETE','/ut/game/fifa21/squad/2');obj.conn.commit();obj.conn.close()
if __name__=='__main__':unittest.main()
