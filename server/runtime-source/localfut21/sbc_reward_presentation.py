"""Native completion reward payloads. Presentation only, never grants items."""
import copy
import re

def award(s,entry):
 result=copy.deepcopy(entry)
 if result.get('type',result.get('awardType'))=='pack':
  pid=int(result.get('packId',result.get('value',0)) or 0)
  # Native SBC reward decoder reads halId, count, value and untradeable.
  # assetId/packAssetId alone are not used by this decoder.
  result['halId']=int(s._pack_art_id(pid))
  result.pop('itemData',None)
 return result

def response(s,method,path,result):
 if method!='PUT' or not re.fullmatch(r'/ut/game/fifa21/sbs/challenge/\d+',path) or result[0]!=200:return result
 document=s.safe_json(result[2])
 if not isinstance(document,dict) or not document.get('success'):return result
 cid=int(document['challengeId']);challenge=s._SBC_CHAL_BY_INT.get(cid,{})
 sid=int(document.get('setId',0));group=s._SBC_SET_BY_INT.get(sid,{})
 complete=bool(group.get('challenges')) and all(str(c['id']) in s._sbc_completed() for c in group['challenges'])
 # A single-challenge set has one entitlement. Route its existing reward to
 # the group completion screen; never duplicate it in both award lists.
 if (complete or (cid==910501 and document.get('completed'))) and len(group['challenges'])==1 and not document.get('grantedSetAwards'):
  document['grantedSetAwards']=document.get('grantedChallengeAwards',[])
  document['grantedChallengeAwards']=[]
 groups=[]
 for key in ('grantedChallengeAwards','grantedSetAwards'):
  entries=[award(s,x) for x in document.get(key,[]) if isinstance(x,dict)]
  document[key]=entries;groups.extend(entries)
 # Also keep the compatibility preview lists consistent with the native lists.
 document['awards']=copy.deepcopy(groups);document['rewards']=copy.deepcopy(groups)
 s.log.info('SBC COMPLETION PREVIEW challenge=%s name=%s set=%s setName=%s challengeAwards=%s setAwards=%s',
  cid,challenge.get('name',''),sid,group.get('name',''),
  [(x.get('type'),x.get('value'),x.get('halId'),x.get('count')) for x in document['grantedChallengeAwards']],
  [(x.get('type'),x.get('value'),x.get('halId'),x.get('count')) for x in document['grantedSetAwards']])
 return result[0],result[1],s.json_bytes(document)
