import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i in range(120):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
hits={}
def h(uc,a,s,u):
    hits[a]=hits.get(a,0)+1
# a single hook only, over the .text
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, d[BLOCK_OFFSET+120*BLOCK_SIZE:BLOCK_OFFSET+121*BLOCK_SIZE])
print("distinct addrs executed:",len(hits))
import collections
lo=collections.Counter()
for a,c in hits.items(): lo[(a>>8)<<8]+=c
for base in sorted(lo):
    if 0x10002000<=base<0x10006000: print("  %08x: %d"%(base,lo[base]))
for a in (0x10005520,0x10005390,0x10005080,0x10002cc0,0x100030e0,0x10002f80,0x10009520):
    print("  %08x -> %d"%(a,hits.get(a,0)))
