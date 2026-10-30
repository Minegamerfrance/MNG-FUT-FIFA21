"""Execute the real retail comparator in an isolated process with fake cards."""
import ast,ctypes as c,functools,json,os,random,re,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if sys.platform!='win32':
 print('SKIP native x64 execution requires Windows');raise SystemExit(0)
server=ROOT/'server'
filename=Path(os.environ.get('FIFA_INSPECT_BINARY',r'C:/Program Files/EA Games/FIFA 21/CardsDLL_Win64_retail.dll'))
if not filename.exists():
 print('SKIP set FIFA_INSPECT_BINARY to a supported retail CardsDLL');raise SystemExit(0)
binary=filename.read_bytes()
pe=struct.unpack_from('<I',binary,0x3c)[0]
optional=struct.unpack_from('<H',binary,pe+20)[0]
sections=[]
for i in range(struct.unpack_from('<H',binary,pe+6)[0]):
 at=pe+24+optional+i*40
 size,address,rawsize,offset=struct.unpack_from('<IIII',binary,at+8)
 sections.append((address,rawsize,offset))
def offset_for(address):
 for start,size,offset in sections:
  if start<=address<start+size:return offset+address-start
 raise ValueError(address)
source=(server/'FIFA21-PackSort.cs').read_text()
original=bytes.fromhex(re.search(r'const string Original="([0-9a-f]+)"',source)[1])
replacement=bytes.fromhex(re.search(r'const string Replacement="([0-9a-f]+)"',source)[1])
assert len(original)==len(replacement)==35
start=0x2375c0;code=bytearray(binary[offset_for(start):offset_for(0x237727)])
assert code[0x23768b-start:0x2376ae-start]==original
# Redirect the only RIP-relative global sentinel load into our own allocation.
struct.pack_into('<i',code,0x2375f0-start+3,0x800-(0x2375f0-start+7))
k=c.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[c.c_void_p,c.c_size_t,c.c_ulong,c.c_ulong];k.VirtualAlloc.restype=c.c_void_p
k.VirtualProtect.argtypes=[c.c_void_p,c.c_size_t,c.c_ulong,c.POINTER(c.c_ulong)];k.VirtualProtect.restype=c.c_bool
memory=k.VirtualAlloc(None,0x4000,0x3000,4);assert memory
c.memmove(memory,bytes(code),len(code));patched=bytearray(code);patched[0x23768b-start:0x2376ae-start]=replacement
c.memmove(memory+0x1000,bytes(patched),len(patched));struct.pack_into('<i',patched,0x2375f0-start+3,0x800-(0x2375f0-start+7))
# Both functions have their own zero sentinel at +0x800.
old=c.c_ulong();assert k.VirtualProtect(memory,0x2000,0x20,c.byref(old))
Compare=c.WINFUNCTYPE(c.c_bool,c.c_void_p,c.c_void_p,c.c_void_p)
old_compare=Compare(memory);new_compare=Compare(memory+0x1000)
parsed=ast.parse((server/'runtime-source/localfut21/server.py').read_text(encoding='utf-8-sig'))
key=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name=='_pack_reveal_sort_key')
space={};exec(compile(ast.Module(body=[key],type_ignores=[]),'sort-key','exec'),space);sort_key=space['_pack_reveal_sort_key']
def card(resource,rating,rarity,stamp,discard=700,paid=0,kind=1,duplicate=False):
 obj=c.create_string_buffer(0x200);handle=c.create_string_buffer(0x18)
 struct.pack_into('<QQ',obj,8,100000+resource,123 if duplicate else 0)
 struct.pack_into('<I',obj,0x18,resource);struct.pack_into('<I',obj,0x28,stamp)
 struct.pack_into('<II',obj,0x38,discard,paid);struct.pack_into('<I',obj,0x4c,kind)
 struct.pack_into('<Q',handle,0x10,c.addressof(obj))
 return dict(resourceId=resource,rating=rating,rareflag=rarity,itemType='player',obj=obj,handle=handle)
def compare(fn,left,right):return fn(None,c.addressof(left['handle']),c.addressof(right['handle']))
# Reproduce the screenshot: equal quick-sell values force resource ordering.
a=card(100,78,1,1700000000);b=card(200,90,1,1700000001)
assert compare(old_compare,a,b) and not compare(old_compare,b,a)
assert compare(new_compare,b,a) and not compare(new_compare,a,b)
items=[card(rating*1000+rarity,rating,rarity,0,15000 if rarity>1 else 700) for rating,rarity in [(85,22),(87,3),(91,1),(79,1),(85,12),(88,1),(81,0)]]
expected=sorted(items,key=sort_key)
for rank,item in enumerate(expected):struct.pack_into('<I',item['obj'],0x28,1700000100-rank)
for seed in range(100):
 shuffled=random.Random(seed).sample(items,len(items))
 got=sorted(shuffled,key=functools.cmp_to_key(lambda a,b:-1 if compare(new_compare,a,b) else 1))
 assert [i['resourceId'] for i in got]==[i['resourceId'] for i in expected]
# All paths outside the player/player comparison stay identical.
for kind1 in (1,2,3,4,6,9):
 for kind2 in (1,2,3,4,6,9):
  if kind1==kind2==1:continue
  a=card(101,85,1,1700000000,kind=kind1);b=card(202,90,1,1700000001,kind=kind2)
  assert compare(old_compare,a,b)==compare(new_compare,a,b),(kind1,kind2)
print('PASS: real x64 comparator, screenshot regression, 100 mixed-event pack permutations, non-player paths unchanged.')
