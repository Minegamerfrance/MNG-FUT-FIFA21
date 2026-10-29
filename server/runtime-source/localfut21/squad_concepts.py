"""Derive concept status from slots and resolve concepts to owned instances."""
from copy import deepcopy

def reconcile(squad, owned, concept_base):
    result=deepcopy(squad)
    players=result.get('players',[])
    if not isinstance(players,list):players=[]
    def iid(slot):
        data=slot.get('itemData') if isinstance(slot.get('itemData'),dict) else {}
        try:return int(slot.get('itemId',slot.get('id',data.get('id',0))) or 0)
        except (ValueError,TypeError):return 0
    available={}
    for item in owned:
        if item.get('itemType','player')!='player' or item.get('pile') not in ('club','squad'):continue
        available.setdefault(int(item.get('resourceId',0) or 0),[]).append(item)
    used={iid(slot) for slot in players if isinstance(slot,dict) and not concept_base < iid(slot) < concept_base+200000000}
    has_concept=False
    for slot in players:
        if not isinstance(slot,dict):continue
        identity=iid(slot)
        if not concept_base < identity < concept_base+200000000:continue
        item=next((i for i in available.get(identity-concept_base,[]) if int(i['id']) not in used),None)
        if item:
            identity=int(item['id']);used.add(identity)
            slot.pop('id',None);slot.pop('itemData',None)
            slot.update(itemId=identity,dream=False)
        else:has_concept=True
    result['squadType']='DREAM_SQUAD' if has_concept else 'REGULAR_SQUAD'
    return result
