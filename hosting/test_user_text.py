import ast,unittest
from pathlib import Path
from types import SimpleNamespace
p=Path(__file__).resolve().parents[1]/'server/runtime-source/localfut21/server.py';tree=ast.parse(p.read_text(encoding='utf-8-sig'))
ns={'Fire2Packet':object}
for n in tree.body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('_TDF_') for t in n.targets):exec(compile(ast.Module(body=[n],type_ignores=[]),str(p),'exec'),ns)
for n in tree.body:
 if isinstance(n,ast.FunctionDef) and n.name.startswith('_tdf_'):exec(compile(ast.Module(body=[n],type_ignores=[]),str(p),'exec'),ns)
f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_fire2_local_response')
f.body=[f.body[0],next(n for n in f.body if isinstance(n,ast.If) and ast.unparse(n.test)=='(c, k) == (9, 20)')]
exec(compile(ast.fix_missing_locations(ast.Module(body=[f],type_ignores=[])),str(p),'exec'),ns)
class Text(unittest.TestCase):
 def test_captured_name_request(self):
  packet=SimpleNamespace(component=9,command=20,payload=bytes.fromhex('d2ccf4040301929cb40002d74e3401084d4e47204655540000'))
  response,label=ns['_fire2_local_response'](packet)
  self.assertEqual(label,'Util.FilterForProfanity');self.assertEqual(ns['_tdf_get_string'](response,'UTXT'),'MNG FUT');self.assertEqual(ns['_tdf_get_int'](response,'DIRT'),0)
  self.assertTrue(response.startswith(ns['_tdf_tag']('TLST',ns['_TDF_LIST'])+bytes([ns['_TDF_GROUP'],1])))
if __name__=='__main__':unittest.main()
