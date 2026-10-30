"""Pack purchase and unassigned refresh use one non-destructive display order."""
import ast,copy,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ast.parse((ROOT/'server/runtime-source/localfut21/server.py').read_text(encoding='utf-8-sig'))
functions=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('_pack_reveal_sort_key','_pack_display_items')]
namespace={'now_s':lambda:1700000000}
exec(compile(ast.Module(body=functions,type_ignores=[]),'server.py','exec'),namespace)
class PackDisplay(unittest.TestCase):
 def test_events_by_rating_then_rare_gold_then_other_players(self):
  cards=[dict(id=i,resourceId=i+100,rating=rating,rareflag=rarity,timestamp=1500000000+i,discardValue=700,lastSalePrice=5000,contract=17)
    for i,(rating,rarity) in enumerate([(90,1),(85,22),(87,3),(85,12),(79,1),(82,0)])]
  original=copy.deepcopy(cards)
  display=namespace['_pack_display_items'](cards)
  self.assertEqual([c['id'] for c in display],[2,1,3,0,4,5])
  self.assertEqual([c['timestamp'] for c in display],list(range(1700000000,1699999994,-1)))
  self.assertEqual(cards,original)
  for item in display:
   saved=original[item['id']]
   self.assertEqual({k:v for k,v in item.items() if k!='timestamp'},{k:v for k,v in saved.items() if k!='timestamp'})
 def test_refresh_combines_multiple_packs_without_losing_duplicates(self):
  a=dict(id=1,resourceId=200,rating=80,rareflag=1,timestamp=1690000000)
  b=dict(id=2,resourceId=300,rating=91,rareflag=1,timestamp=1600000000)
  duplicate=dict(b,id=3,duplicate=True)
  got=namespace['_pack_display_items']([a,b,duplicate])
  self.assertEqual([c['id'] for c in got],[2,3,1]);self.assertTrue(got[1]['duplicate'])
if __name__=='__main__':unittest.main()
