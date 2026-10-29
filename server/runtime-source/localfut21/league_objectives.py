import remote_assets
"""Persistent League Telles objectives, based on the XI at match creation."""
import re
import uuid
import json
import struct
import mollet_objectives
from player_objectives import Campaign

CATEGORY = 70
GROUP = 7001
PLAYER = 84098542
KEY = 'league_telles_v1'
GROUPS = {
    7001: dict(player=PLAYER,key=KEY,name='Alex Telles',league=13,nation=54,club=11,
               leagueName='Premier League',nationName='brésiliens',clubName='Manchester United'),
    7002: dict(player=84102432,key='league_brozovic_v1',name='Brozović',league=31,nation=10,club=44,
               leagueName='Serie A',nationName='croates',clubName='l’Inter'),
    7003: dict(player=84088451,key='league_meunier_v1',name='Meunier',league=19,nation=7,club=22,
               leagueName='Bundesliga',nationName='belges',clubName='Dortmund'),
    7004: dict(player=84075655,key='league_muniain_v1',name='Muniain',league=53,nation=45,club=448,
               leagueName='LaLiga',nationName='espagnols',clubName='l’Athletic Club'),
    7005: dict(player=84095368,key='league_mollet_v1',name='Mollet',league=16,nation=18,club=70,
               leagueName='Ligue 1',nationName='français',clubName='Montpellier'),
}
BACKGROUND_GUID = 'd479de87-00e3-43f9-a6f1-55e4ec4cb085'

def background(s, path):
    match=re.fullmatch(r'/fut/items/images/backgrounds/itembgs/([a-f0-9-]+)/(cards_bg_[scej]_1_(38|63|85|98)_0.dds)',path)
    if not match: return None
    rarity=int(match.group(3))
    spec=json.loads((s.ROOT/'custom-backgrounds'/f'rarity{rarity}.json').read_text(encoding='utf8'))
    if match.group(1)!=spec['guid']: return None
    data=remote_assets.read((s.ROOT/'custom-backgrounds'/match.group(2)))
    height,width=struct.unpack_from('<II',data,12)
    assert data[:4]==b'DDS ' and data[84:88]==b'DXT5'
    assert 0<width<=1024 and 0<height<=1024
    linear=((width+3)//4)*((height+3)//4)*16
    assert len(data)==128+linear and struct.unpack_from('<I',data,20)[0]==linear
    return data

def tunables(s, body):
    document=json.loads(body)
    for rarity in (38,63,85,98):
        spec=json.loads((s.ROOT/'custom-backgrounds'/f'rarity{rarity}.json').read_text(encoding='utf8'))
        document['rarities']=[x for x in document['rarities'] if x['id']!=rarity]+[spec]
    return json.dumps(document,ensure_ascii=True).encode('utf8')

CAMPAIGNS={}
for gid,spec in GROUPS.items():
    league=spec['leagueName']
    config=dict(spec,key='league_mollet_v2' if gid==7005 else spec['key'].replace('_v1','_v2'),
        oldKey=spec['key'],title='League '+spec['name'],priority=gid-7000)
    rows=tuple((title.replace('Ligue 1',league),target,pack,desc.replace('Ligue 1',league))
               for title,target,pack,desc in mollet_objectives.CHALLENGES)
    config.update(title='Joueur de '+league,displayOrder=[0,1,2,4,3],
        subTitle='Réussissez cette série d’objectifs pour gagner le joueur '+league+' et des récompenses non-échangeables.')
    # LaLiga already includes its article; retain the same title pattern
    # as Mollet without producing 'La LaLiga en force'.
    rows=tuple((('LaLiga en force' if title=='La LaLiga en force' else title),target,pack,desc)
               for title,target,pack,desc in rows)
    CAMPAIGNS[gid]=Campaign(gid,config,rows)

RULEBREAKERS_CATEGORY=71
GIGNAC_GROUP=7101
CAMPAIGNS[GIGNAC_GROUP]=Campaign(GIGNAC_GROUP,
    dict(player=67262108,key='rulebreakers_gignac_v1',title='Rulebreakers Gignac',
         leagueName='Tigres · Liga MX · France',priority=1,subTitle='Accomplissez ces défis effrayants pour obtenir Gignac Rulebreakers !'),(
    ('La connexion française',10,521,'Adressez 10 passes décisives avec des joueurs français en Clashs d’équipes ou Rivals.'),
    ('Créateurs de Liga MX',8,521,'Adressez 8 passes décisives avec des joueurs de Liga MX en Clashs d’équipes ou Rivals.'),
    ('Les Tigres à la passe',5,521,'Adressez 5 passes décisives avec des joueurs des Tigres de la UANL en Clashs d’équipes ou Rivals.'),
    ('Un nouveau meneur',6,521,'Adressez au moins une passe décisive avec un joueur au poste MOC dans 6 matchs distincts en Clashs d’équipes ou Rivals.'),
    ('Le collectif mexicain',5,521,'Remportez 5 matchs en Clashs d’équipes ou Rivals avec au moins 3 titulaires de Liga MX et une passe décisive d’un MOC dans chaque match.'),
    ('La touche de Gignac',4,521,'Remportez 4 matchs en Clashs d’équipes ou Rivals avec au moins un titulaire des Tigres et une passe décisive d’un joueur français dans chaque match.'),
    ),xp=25,group_xp=100,event=True)

from scary_nights import Nights
CAMPAIGNS[7102]=Nights()
from pumpkin_objectives import Pumpkins
CAMPAIGNS[8003]=Pumpkins()
from ballon_dor_objectives import BallonDor,DembeleBallonDor,RodriBallonDor
CAMPAIGNS[7201]=BallonDor()
CAMPAIGNS[7202]=DembeleBallonDor()
CAMPAIGNS[7203]=RodriBallonDor()

def progress(s,group_id=GROUP):return CAMPAIGNS[group_id].progress(s)
def group(s,details=True,group_id=GROUP):return CAMPAIGNS[group_id].group(s,details)
def claim(s,group_id=GROUP):return CAMPAIGNS[group_id].claim(s)

def category(s):
    groups=[group(s,True,gid) for gid in reversed(GROUPS)]
    return dict(categoryId=CATEGORY,id=CATEGORY,name='League',priority=1,groupsList=groups,groups=groups)

def event_category(s):
    groups=[group(s,True,7102),group(s,True,GIGNAC_GROUP),group(s,True,8003)]
    return dict(categoryId=RULEBREAKERS_CATEGORY,id=RULEBREAKERS_CATEGORY,name='Rulebreakers',priority=3,groupsList=groups,groups=groups)

def mng_category(s):
    # Retain the category/group identifiers so existing progress and locks stay valid.
    groups=[group(s,True,7201),group(s,True,7202),group(s,True,7203)]
    return dict(categoryId=72,id=72,name='Ballon d’Or',priority=4,groupsList=groups,groups=groups)

def route(s,method,path):
    match=re.fullmatch(r'/ut/game/fifa21/scmp/(?:active|learning|world)/category/(70|71|72)/details',path)
    if match:
        cat={70:category,71:event_category,72:mng_category}[int(match.group(1))](s)
        return 200,dict(categoryId=cat['categoryId'],groupsList=cat['groupsList'])
    match=re.fullmatch(r'/ut/game/fifa21/scmp/campaign/group/(\d+)(?:/objective/(\d+))?/rewards',path)
    if match and method in ('POST','PUT'):
        gid=int(match.group(1))
        if gid not in CAMPAIGNS:return None
        campaign=CAMPAIGNS[gid]
        index=int(match.group(2))-gid*100-1 if match.group(2) else None
        if index is not None and index not in range(len(campaign.rows)):return 404,dict(reason='UNKNOWN_OBJECTIVE')
        return campaign.claim(s,index)
    return None

def reset(s):
    for campaign in CAMPAIGNS.values():campaign.reset(s)
def start(s,payload,response):
    for campaign in CAMPAIGNS.values():campaign.start(s,payload,response)
def finish(s,payload):
    for campaign in CAMPAIGNS.values():campaign.finish(s,payload)
