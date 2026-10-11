import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
log=[]; rec={}
def h(uc,a,s,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x100029c0:
        a1,a2,a5=o.r32(esp+4),o.r32(esp+8),o.r32(esp+0x14)
        if a2==0x10023a5c: rec['out']=a1; rec['scr']=a5
    if a==0x1000e6f9 and rec.get('out'):
        sc=rec['scr']; base=(sc+20+3)&~3
        idx=[o.r32(base-20+4*i) for i in range(5)]
        sg=[o.r32(base+4*i) for i in range(5)]
        out=struct.unpack("<8f", bytes(o.uc.mem_read(rec['out'],32)))
        log.append((hex(rec['out']),hex(sc),idx,sg,["%.5g"%x for x in out]))
        if len(log)>=5: rec['out']=0
    if a==0x1000e70f: rec['out']=0
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x100029c0,end=0x100029c1)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e6f9,end=0x1000e6fa)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e70f,end=0x1000e710)
o.decode(ctx, d[BLOCK_OFFSET:BLOCK_OFFSET+BLOCK_SIZE])
for e in log: print(e)
