import remote_assets
"""Allowlisted Squad Battles featured banners, using the native image provider."""
from pathlib import PurePosixPath
NAMES=frozenset(('mng_rulebreakers1_v1.dds','mng_totw1_v1.dds'))
PREFIXES=('/squadbattle/cmn/', '/contentfifa/squadbattle/cmn/', '/content/fifa/squadbattle/cmn/', '/contentfifa/ui/external/ion_fut/imgassets/banners/futfeaturedbattlesquad/')
def asset(s,method,path):
    if method!='GET':return None
    name=next((path[len(prefix):] for prefix in PREFIXES if path.startswith(prefix)),None)
    if name not in NAMES:return None
    return 200,{'Content-Type':'image/vnd-ms.dds','Cache-Control':'public, max-age=86400'},remote_assets.read((s.ROOT/'custom-featuredbanners'/name))
