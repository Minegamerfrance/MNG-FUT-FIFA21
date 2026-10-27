"""The requested store offers; reward packs remain independently openable."""
import copy

# id, name, group, coin price, FIFA points, items, rares
OFFERS=(
 (100,'Pack bronze','bronze',400,0,12,1),
 (101,'Pack premium bronze','bronze',750,0,12,3),
 (200,'Pack argent','silver',2500,0,12,1),
 (202,'Pack premium argent','silver',3750,75,12,3),
 (300,'Pack or','gold',5000,100,12,1),
 (301,'Pack premium or','gold',7500,150,12,3),
 (303,'Pack jumbo premium or','gold',15000,300,24,7),
 (403,'Pack méga','special',35000,700,30,18),
 (404,'Pack méga rare','special',55000,1100,30,30),
 (405,'Pack ultime','special',125000,2500,30,30),
)

def points(s):return max(0,int(s.STATE.get('fifa_points',0) or 0))

def apply(s):
 if getattr(s,'_classic_store_applied',False):return
 s._classic_store_applied=True
 original_settings=s.load_pack_settings
 def settings():
  result=copy.deepcopy(original_settings())
  for cfg in result['packs'].values():cfg['enabled']=False
  allowed=set(s.CATALOG_POLICY.get('allowedRarities',[0,1,3,12,21,22]))-set(s.CATALOG_POLICY.get('disabledRarities',[]))
  for pid,name,group,price,fp,size,rare in OFFERS:
   tier=group if group!='special' else 'gold'
   flags=[0,1] if tier!='gold' else sorted(allowed & {0,1,3,12,21,22})
   result['packs'][str(pid)]=dict(enabled=True,name=name,
    bio=f'Contient {size} éléments, dont {rare} '+('rare.' if rare==1 else 'rares.'),
    price=price,points_price=fp,size=size,rare_slots=rare,store_group=group,
    gold_weight=100 if tier=='gold' else 0,silver_weight=100 if tier=='silver' else 0,
    bronze_weight=100 if tier=='bronze' else 0,manager_chance=0,
    special_chance=0.05 if tier=='gold' else 0,guaranteed_specials=0,
    allowed_rareflags=flags,special_weights={'3':100,'12':2,'21':100,'22':100})
  return result
 s.load_pack_settings=settings
 original_groups=s._store_purchasegroups
 def groups():
  result=original_groups();offers={row[0]:row for row in OFFERS}
  for pack in result['purchase']:
   if pack.get('isOwned') or pack.get('displayGroup',{}).get('value') not in ('bronze','silver','gold','special'):continue
   if pack['id'] not in offers:continue
   pid,name,group,price,fp,size,rare=offers[pack['id']]
   art=s._pack_art_id(pid)
   pack.update(assetId=art,packAssetId=art,packAssetID=str(art),numberItems=size,numItems=size,rare=rare,
    price=price,coins=price,coinPrice=price,points=fp,pointsPrice=fp,
    isPurchaseable=s.STATE.credits()>=price or fp>0 and points(s)>=fp)
   pack['currencies']=[dict(name='coins',funds=price,finalFunds=price)]
   if fp:pack['currencies'].append(dict(name='points',funds=fp,finalFunds=fp))
  return result
 s._store_purchasegroups=groups
 def info():
  packs=[p for p in groups()['purchase'] if p.get('displayGroup',{}).get('value') in ('bronze','silver','gold','special')]
  return dict(storeEnabled=True,cardPackStoreEnabled=True,packList=packs,packTypes=packs,credits=s.STATE.credits())
 s.store_info=info
