import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_ESP, UC_X86_REG_EBX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
last=[0]; ev=[]
def hc(uc,a,s,u): last[0]=a
def hw(uc,acc,addr,size,val,u):
    if 0x30012a20<=addr<0x30012a40:
        ev.append((hex(last[0]),hex(addr),struct.unpack("<f",struct.pack("<I",val))[0]))
o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=0x30012a20,end=0x30012a40)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
from collections import Counter
print(Counter(p for p,_,_ in ev))
print(ev[:12])
