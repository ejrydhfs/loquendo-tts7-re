import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_ECX, UC_X86_REG_EAX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
cnt={'cb':0,'nz':0,'ec0':0,'mode':[]}
def h(uc,a,s,u):
    if a==0x1000e66d: cnt['cb']+=1
    if a==0x1000e5da: cnt['nz']+=1
    if a==0x10002ec0: cnt['ec0']+=1
    if a==0x1000e5cd:
        obj=uc.reg_read(UC_X86_REG_ESI)
        if obj in (o16,o32): cnt['mode'].append((hex(obj),hex(uc.reg_read(UC_X86_REG_ECX)),o.r32(uc.reg_read(UC_X86_REG_ECX)+0x28)))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
print(cnt['cb'], cnt['nz'], cnt['ec0'])
print(cnt['mode'][:10])
