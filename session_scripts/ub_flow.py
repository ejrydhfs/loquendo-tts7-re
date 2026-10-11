import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
seq=[]
def h(uc,a,s,u):
    if 0x1000e5d0<=a<0x1000e820:
        seq.append((a,uc.reg_read(UC_X86_REG_ESI)))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e5d0,end=0x1000e820)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
# print addresses for the o16 object only, first 120
out=[(hex(a),'o16' if es==o16 else ('o32' if es==o32 else hex(es))) for a,es in seq]
from collections import Counter
print(Counter(a for a,_ in out if a in ('0x1000e68c','0x1000e674','0x1000e695','0x1000e66d','0x1000e5da')))
k=0
for a,es in out:
    if es=='o16':
        print(a,end=' '); k+=1
        if k>110: break
print()
