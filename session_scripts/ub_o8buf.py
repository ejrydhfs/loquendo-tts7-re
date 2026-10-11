import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
last=[0]; ev=[]
def hc(uc,a,s,u): last[0]=a
def hw(uc,acc,addr,size,val,u):
    if 0x30012800<=addr<0x30012a30 and size==4:
        ev.append((hex(last[0]),hex(addr),struct.unpack("<f",struct.pack("<I",val))[0]))
o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=0x30012800,end=0x30012a30)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
from collections import Counter
print(Counter(p for p,_,_ in ev))
print("first 12:",ev[:12])
print("o8[+48]:",["%.6g"%x for x in fl(o.r32(o8+0x48),40)])
print("o8[+40]:",["%.6g"%x for x in fl(o.r32(o8+0x40),10)])
