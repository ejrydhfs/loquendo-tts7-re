import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
NF=38
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
for i in range(NF):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
R={n:o.uc.reg_read(r) for n,r in [('eax',UC_X86_REG_EAX),('ebx',UC_X86_REG_EBX),('ecx',UC_X86_REG_ECX),('edx',UC_X86_REG_EDX),('esi',UC_X86_REG_ESI),('edi',UC_X86_REG_EDI),('ebp',UC_X86_REG_EBP),('esp',UC_X86_REG_ESP)]}
def f(uc,a,s,u):
    if a in (0x1000e394,0x1000e3a1,0x1000e3a5,0x1000e3a9,0x1000e3ad,0x1000e3e3,0x1000e4a6,0x1000e4d1,0x1000e4a1,0x1000e375):
        esp=uc.reg_read(UC_X86_REG_ESP)
        print("pc=%08x esp=%08x eax=%08x ebx=%08x ecx=%08x edx=%08x edi=%08x ebp=%08x esi=%08x"%(a,esp,uc.reg_read(UC_X86_REG_EAX),uc.reg_read(UC_X86_REG_EBX),uc.reg_read(UC_X86_REG_ECX),uc.reg_read(UC_X86_REG_EDX),uc.reg_read(UC_X86_REG_EDI),uc.reg_read(UC_X86_REG_EBP),uc.reg_read(UC_X86_REG_ESI)))
o.uc.hook_add(UC_HOOK_CODE,f,begin=0x1000e170,end=0x1000e8f0)
o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
