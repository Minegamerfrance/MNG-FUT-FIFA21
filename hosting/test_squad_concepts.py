import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server/runtime-source/localfut21'))
from squad_concepts import reconcile
class Concepts(unittest.TestCase):
 def test_transition_and_acquisition(self):
  base=600000000000
  squad={'id':2,'players':[{'index':0,'itemData':{'id':base+123,'dream':True}}]}
  self.assertEqual(reconcile(squad,[],base)['squadType'],'DREAM_SQUAD')
  self.assertEqual(reconcile({'id':2,'players':[]},[],base)['squadType'],'REGULAR_SQUAD')
  item={'id':9001,'resourceId':123,'itemType':'player','pile':'unassigned'}
  self.assertEqual(reconcile(squad,[item],base)['squadType'],'DREAM_SQUAD')
  item['pile']='club';owned=reconcile(squad,[item],base)
  self.assertEqual(owned['squadType'],'REGULAR_SQUAD');self.assertEqual(owned['players'][0]['itemId'],9001)
  self.assertTrue(squad['players'][0]['itemData']['dream'])
 def test_no_duplicate_or_wrong_version(self):
  b=600000000000;s={'players':[{'itemId':9001},{'itemId':b+123}]};items=[{'id':9001,'resourceId':123,'pile':'club'}]
  self.assertEqual(reconcile(s,items,b)['squadType'],'DREAM_SQUAD')
  items[0]['resourceId']=124
  self.assertEqual(reconcile({'players':[{'itemId':b+123}]},items,b)['squadType'],'DREAM_SQUAD')
if __name__=='__main__':unittest.main()
