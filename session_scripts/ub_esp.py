import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
NF=38
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
for i in range(NF):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
stack={}
def hook(uc,addr,size,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    if addr==0x1000e170:
        stack.setdefault(esp,[]).append(uc.reg_read(UC_X86_REG_ESI))
    if addr==0x1000e623:
        print("noise loop esp=%08x  (E offsets: %s)"%(esp, {hex(k-esp):v for k,v in sorted(stack.items())}))
    if addr==0x1000e66d:
        print("cb branch  esp=%08x  (E offsets: %s)"%(esp, {hex(k-esp):v for k,v in sorted(stack.items())}))
o.uc.hook_add(UC_HOOK_CODE,hook,begin=0x1000e170,end=0x1000e690)
o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
