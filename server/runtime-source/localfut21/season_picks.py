"""Season pick tokens use the same native unlock and selection flow as the SBC."""
SPECS={
 3:(80,3,None,'Choix joueur 80+'),7:(80,3,None,'Choix joueur 80+'),
 13:(75,5,3,'Choix joueur TOTW'),17:(75,5,3,'Choix joueur TOTW'),
 23:(75,2,22,'Choix joueur Rulebreakers'),27:(75,2,22,'Choix joueur Rulebreakers'),
}

def candidates(s,level):
 minimum,count,rarity,_=SPECS[level]
 return [rid for rid,m in s.PLAYER_DB.items() if int(m.get('rating',0))>=minimum
     and m.get('packEligible',True) and s.aqua_pro_resource_id(rid) is None
     and (rarity is None or int(m.get('rareflag',0))==rarity)]

def token(s,level,item_id):
 minimum,count,rarity,name=SPECS[level];pool=candidates(s,level)
 if len(pool)<count:raise ValueError('Insufficient season pick candidates')
 rid=pool[0]
 result=dict(id=item_id,timestamp=s.now_s(),resourceId=rid,assetId=rid,carddbid=rid,
     cardassetid=34,itemType='misc',cardsubtypeid=237,subtype=237,subType=237,
     itemState='free',stackCount=1,untradeableCount=1,untradeable=True,owners=1,
     pile='unassigned',rating=minimum,rareflag=23,discardValue=0,
     name=f'{name} (1 sur {count})',description=f'1/{count}',IS_UNLOCKABLE=True,
     UNLOCKABLE_TYPE='PLAYER_PICK',CARD_TYPE='UNLOCKS',cardType='UNLOCKS',
     card_type='UNLOCKS',UNLOCKS=[],choiceCount=count,minRating=minimum,
     sourcePackId=526,resourceGameYear=2021,seasonLevel=level)
 if rarity is not None:result['allowedRarities']=[rarity]
 return result

def award(s,level):
 item=s._native_pack_item(token(s,level,0));rid=item['resourceId']
 return dict(type='item',awardType='item',halId=0,assetId=rid,value=rid,awardValue=rid,
     count=1,awardCount=1,isItem=True,isPack=False,isPlayerPick=True,
     choiceCount=item['choiceCount'],minRating=item['minRating'],
     untradeable=True,isUntradeable=True,name=item['name'],items=item['name'],
     itemsAmount=1,itemData=item)
