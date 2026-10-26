"""Explicit temporary no-cost completion transport diagnostic.

Only the configured challenge is intercepted. No squad, inventory, XP or pack
state is changed. Remove the runtime configuration to disable the diagnostic.
"""
import json
import re

def route(s,method,path):
 cfgfile=s.RUNTIME_ROOT/'data/sbc-completion-probe.json'
 if not cfgfile.exists():return None
 cfg=json.loads(cfgfile.read_text(encoding='utf8'))
 cid=int(cfg['challengeId'])
 if method!='PUT' or path not in (f'/ut/game/fifa21/sbs/challenge/{cid}',f'/ut/game/fifa21/sbs/challenge/{cid}/squad'):return None
 if path.endswith('/squad'):return 200,{},s.json_bytes({})
 reward=dict(type='pack',value=523,halId=51,count=1,isUntradeable=True)
 reply=dict(id=cid,challengeId=cid,setId=910100,credits=s.STATE.credits(),
  grantedChallengeAwards=[],grantedSetAwards=[reward],preOrderPacks=len(s.STATE.unopened_pack_ids()),recoveredPacks=0,
  success=False,completed=False)
 s.log.info('SBC DIAGNOSTIC NO CONSUMPTION challenge=%s reply=%s',cid,reply)
 (s.RUNTIME_ROOT/'data/sbc-completion-probe-result.json').write_text(json.dumps(reply),encoding='utf8')
 return 200,{'Cache-Control':'no-store'},s.json_bytes(reply)
