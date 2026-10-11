import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
for NF,label in ((0,'frame 0'),(38,'frame 38')):
    o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
    for i in range(NF): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    info=[]
    def h(uc,a,s,u):
        if a==0x1000e68c:
            b=bytes(uc.mem_read(0x1000e68c,5)); rel=struct.unpack("<i",b[1:5])[0]
            info.append(('at-call',b.hex(),hex(0x1000e691+rel),hex(uc.reg_read(UC_X86_REG_ESI))))
        if a==0x100105c0:
            sp=uc.reg_read(UC_X86_REG_ESP); info.append(('at-105c0','ret='+hex(o.r32(sp))))
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
    o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
    print(label, info[:6])
