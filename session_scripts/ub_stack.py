import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
NF=38
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
for i in range(NF):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
last=[0]; log=[]
def hcode(uc,a,s,u): last[0]=a
def hw(uc,acc,addr,size,val,u):
    if 0x201fe540<=addr<0x201fe570:
        log.append((last[0],hex(addr),hex(val)))
o.uc.hook_add(UC_HOOK_CODE,hcode,begin=0x10000000,end=0x10040000)
o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=0x201fe000,end=0x201ff000)
# find the o32 E
o.uc.hook_add(UC_HOOK_CODE, lambda uc,a,s,u: print("o32 entry esp=%08x"%uc.reg_read(UC_X86_REG_ESP)) if a==0x1000e170 else None, begin=0x1000e170,end=0x1000e171)
o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
for e in log: print(e)
