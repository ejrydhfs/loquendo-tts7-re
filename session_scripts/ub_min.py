import sys
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
hits=[]
def h(uc,a,s,u):
    hits.append(hex(a))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002ec0,end=0x10003000)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e680,end=0x1000e6a0)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
from collections import Counter
print(Counter(hits))
