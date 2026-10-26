"""Native club-item season rewards, separate from player-card rewards."""
import fut_inventory

REWARDS={
 6500014:dict(resourceId=6500014,assetId=6500014,carddbid=6500014,
     itemType='vanity',cardsubtypeid=500,vanityType=500,vanitySubTypeId=500,
     family='vanity_tifo',tifoId=6500014,category=1,name='Tifo',
     imageName='tifo_6500014_c'),
 8120213:dict(resourceId=8120213,assetId=213,carddbid=8120213,cardassetid=37,
     itemType='ball',cardsubtypeid=30,family='balls',table='fcc_balls',ballid=213,
     category=1,name='Ballon',imageName='ball_213'),
}

def item(s,rid,item_id):
 value=fut_inventory.cosmetic_item(dict(REWARDS[int(rid)],rating=90,value=90,
     rareflag=1,islocked=0,discardValue=0),item_id,'unassigned')
 value.update(untradeable=True,untradeableCount=1,objectiveReward=True)
 return value

def award(s,rid):
 value=s._native_pack_item(item(s,rid,0))
 return dict(type='item',awardType='item',halId=0,assetId=rid,value=rid,awardValue=rid,
     count=1,awardCount=1,isItem=True,isPack=False,untradeable=True,isUntradeable=True,
     name=value['name'],items=value['name'],itemsAmount=1,itemData=value)
