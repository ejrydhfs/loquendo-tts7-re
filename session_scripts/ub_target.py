import sys
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_EIP
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
prev=[0]; after=[]
def h(uc,a,s,u):
    if prev[0]==0x1000e68c:
        after.append((hex(a),hex(uc.reg_read(UC_X86_REG_ESI))))
    prev[0]=a
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
print("after 0x1000e68c:",after)
