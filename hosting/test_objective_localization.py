"""Six-language coverage and API checks in an isolated temporary club."""
import json,logging,os,re,sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]/'server/runtime-source/localfut21'
sys.path.insert(0,str(ROOT))
from fut_i18n import LANGUAGE,t
import ui_localization as ui

NEUTRAL=set('Alex Telles|Azpilicueta|Babel|Ballon d’Or|Boëtius|Brozović|Buffon|Bundesliga|Cristiano Ronaldo|Cristiano Ronaldo Flashback|Dembélé|Dubois|Gignac|Götze|Kane|Kimmich|Kroos|LaLiga|Ligue 1|Luis Díaz|Léo Dubois|MNG FUT|MNG FUT Kroos|Meunier|Mollet|Muniain|Opara|Paulinho|Premier League|Rodri|Rulebreakers|Rulebreakers Gignac|Rulebreakers Kimmich|Rulebreakers Visca|Serie A|Višća'.split('|'))

class Translation(unittest.TestCase):
 def test_context_isolation_and_locale_memory(self):
  states=[]
  for _ in range(2):
   values={};states.append(SimpleNamespace(STATE=SimpleNamespace(get=lambda k,d=None,v=values:v.get(k,d),set=lambda k,x,v=values:v.__setitem__(k,x)),CFG={}))
  self.assertEqual(ui.request_language(states[0],'//ut/auth',{'Accept-Language':'en-US'},b'{"locale":"pt_BR"}'),'pt')
  self.assertEqual(ui.request_language(states[0],'/ut/game/fifa21/scmp/campaign/active',{}),'pt')
  self.assertEqual(ui.request_language(states[1],'/ut/game/fifa21/scmp/campaign/active',{}),'fr')
  self.assertEqual(ui.request_language(states[0],'/x?locale=de_DE',{'Accept-Language':'pt-PT'}),'de')
  self.assertEqual(ui.request_language(states[0],'/x',{'X-UT-UILanguage':'it_IT'}),'it')
  barrier=threading.Barrier(3);results={}
  def work(lang):
   token=LANGUAGE.set(lang)
   try:
    barrier.wait();results[lang]=[t("L'ascension du maestro Toni Kroos") for _ in range(20)]
   finally:LANGUAGE.reset(token)
  threads=[threading.Thread(target=work,args=(lang,)) for lang in ('fr','pt','de')]
  for thread in threads:thread.start()
  for thread in threads:thread.join()
  self.assertEqual(set(results['pt']),{'A ascensão do maestro Toni Kroos'})
  self.assertEqual(set(results['fr']),{"L'ascension du maestro Toni Kroos"})
  self.assertEqual(set(results['de']),{'Der Aufstieg von Maestro Toni Kroos'})

 def test_display_fields_only(self):
  document=dict(id='L’apprentissage',target=48,currentProgress=7,name='L’apprentissage',
                squad=dict(name='L’apprentissage',players=[dict(id=123,resourceId=67291385)]))
  source=json.dumps(document).encode()
  token=LANGUAGE.set('en')
  try:
   _,headers,body=ui.response(SimpleNamespace(json_bytes=lambda d:json.dumps(d).encode()),
     '/ut/game/fifa21/scmp/campaign/active',(200,{'Content-Length':'1'},source))
   result=json.loads(body)
   self.assertEqual(result['name'],'The apprenticeship')
   self.assertEqual(result['id'],document['id']);self.assertEqual(result['target'],48)
   self.assertEqual(result['squad'],document['squad']);self.assertNotIn('Content-Length',headers)
  finally:LANGUAGE.reset(token)

class NativeApi(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  os.environ['LOCALFUT_RUNTIME_ROOT']=cls.tmp.name
  os.environ['LOCALFUT21_USER_CONFIG_ROOT']=str(Path(cls.tmp.name)/'config')
  os.environ['LOCALFUT_TEST_MODE']='1'
  import server
  logging.getLogger().setLevel(logging.CRITICAL)
  cls.s=server
  cls.s.now_s=lambda:1793356800
 @classmethod
 def tearDownClass(cls):
  cls.s.STATE.conn.close()
  for h in logging.getLogger().handlers[:]:logging.getLogger().removeHandler(h);h.close()
  cls.tmp.cleanup()
 def request(self,path,lang):
  code,headers,body=self.s.route_fut('GET',path,{'X-UT-UILanguage':lang},b'')
  self.assertEqual(code,200);self.assertEqual(headers.get('Content-Language'),lang)
  return json.loads(body)
 def test_coverage_of_all_authored_objectives_and_sbcs(self):
  texts=set()
  def collect(value):
   if isinstance(value,dict):
    for key,child in value.items():
     if key in ui.FIELDS|{'rewardName','leagueName'} and isinstance(child,str) and child.strip():texts.add(child)
     else:collect(child)
   elif isinstance(value,list):
    for child in value:collect(child)
  token=LANGUAGE.set('fr')
  try:
   for c in self.s.league_objectives.CAMPAIGNS.values():
    collect(c.group(self.s));collect(c.spec)
    for row in c.rows:texts.update((row[0],row[3]))
   for gid in self.s.recurring_objectives.GROUPS:collect(self.s.recurring_objectives.group(self.s,gid))
   collect(self.s._scmp_campaign_json())
   for spec in self.s._SBC_SET_BY_INT.values():collect(self.s._sbc_set_json(spec))
   for spec in self.s._SBC_CHAL_BY_INT.values():collect(self.s._sbc_challenge_json(spec))
  finally:LANGUAGE.reset(token)
  for lang in ('en','es','de','it','pt'):
   for text in texts:
    if text in NEUTRAL or re.fullmatch(r'\d+/\d+',text):continue
    translated=ui.translate(text,lang)
    self.assertIsNotNone(translated,(lang,text))
    self.assertNotRegex(translated,r'Disputez|Remportez|Marquez|Adressez|Terminez|joueurs |joueur |titulaire|matchs|en Clashs|obtenir|prêt de|Équipe | avec ')
 def test_native_objectives_and_sbc_requirements_in_six_languages(self):
  def structure(value):
   if isinstance(value,list):return [structure(v) for v in value]
   if not isinstance(value,dict):return value
   return {k:structure(v) for k,v in value.items() if not(k in ui.FIELDS and isinstance(v,str))}
  def differences(left,right,path=''):
   if isinstance(left,dict) and isinstance(right,dict):
    return [diff for k in left for diff in differences(left[k],right.get(k),path+'.'+str(k))]
   if isinstance(left,list) and isinstance(right,list):
    if len(left)!=len(right):return [(path,'different lengths')]
    return [diff for i,(a,b) in enumerate(zip(left,right)) for diff in differences(a,b,path+f'[{i}]')]
   return [] if left==right else [(path,left,right)]
  paths=['/ut/game/fifa21/scmp/campaign/active','/ut/game/fifa21/scmp/active/category/73/details',
         '/ut/game/fifa21/scmp/active/category/70/details','/ut/game/fifa21/sbs/sets']
  kroos=next(gid for gid,spec in self.s._SBC_SET_BY_INT.items() if spec['id']=='MNG_KROOS_75')
  paths.append(f'/ut/game/fifa21/sbs/setid/{kroos}/challenges')
  for path in paths:
   baseline=self.request(path,'fr')
   for lang in ('en','pt','es','de','it'):
    translated=self.request(path,lang)
    self.assertEqual(differences(structure(translated),structure(baseline))[:6],[],(path,lang))
  group=self.request(paths[1],'pt')['groupsList'][0]
  self.assertEqual(group['title'],'A ascensão do maestro Toni Kroos')
  self.assertEqual([o['target'] for o in group['objectives']],[1,48,10,8,20,205,24,27,144])
  self.assertIn('Conclui os 4 elencos',group['objectives'][0]['description'])
  self.assertEqual(self.request(paths[1],'fr')['groupsList'][0]['title'],"L'ascension du maestro Toni Kroos")

if __name__=='__main__':unittest.main()
