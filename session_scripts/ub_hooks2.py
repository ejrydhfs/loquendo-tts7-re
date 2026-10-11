import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
import pefile
DLL="/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/bin/LTTS7Codec210.dll"
pe=pefile.PE(DLL); data=open(DLL,'rb').read()
print("sections:")
for s in pe.sections:
    print("  %-8s VA=%08x vsize=%08x raw=%08x ptr=%08x"%(s.Name.decode().strip('\x00'),
        s.VirtualAddress+0x10000000, s.Misc_VirtualSize, s.SizeOfRawData, s.PointerToRawData))
d=open(BIN,'rb').read()
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i in range(120):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
hits=[]
def h(uc,a,s,u): hits.append(a)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, d[BLOCK_OFFSET+120*BLOCK_SIZE:BLOCK_OFFSET+121*BLOCK_SIZE])
hs=set(hits)
print("total callbacks=%d distinct=%d"%(len(hits),len(hs)))
print("around 0x10009a60-0x10009ab6:",[hex(a) for a in sorted(hs) if 0x10009a60<=a<0x10009ac0])
for va in (0x10009a78,0x10005520,0x10005080):
    mem=bytes(o.uc.mem_read(va,8))
    print("bytes at %08x mem=%s"%(va,mem.hex()))
# what does the call at 0x10009a78 actually do?  find the address right after it in the trace
seq=[a for a in hits if 0x10009a60<=a<0x10009b00]
print("first 60 callbacks in 0x10009a60..:",[hex(a) for a in seq[:60]])
