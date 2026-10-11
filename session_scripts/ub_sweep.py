import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EAX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
def rms(v): return (sum(x*x for x in v)/len(v))**0.5
counts={'loop16':0,'loop32':0,'sub_ret_nonzero':0,'ret16':None}
stack=[]
def h(uc,a,s,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x1000e170:
        stack.append((esp,uc.reg_read(UC_X86_REG_ESI)))
    if a==0x1000e5bc:
        if uc.reg_read(UC_X86_REG_ESI)==o16: counts['loop16']+=1
        else: counts['loop32']+=1
    if a==0x1000e8db:
        # returning: eax=0 or sub_ret; find which frame
        pass
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e170,end=0x1000e171)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e5bc,end=0x1000e5bd)
for i in range(0,42):
    counts['loop16']=0; counts['loop32']=0
    pcm=o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    print("fr %2d pcm=%8.2f exc16=%9.3f exc32=%9.3f syn16=%9.3f syn32=%9.3f A16=%9.3f B16=%8.3f A32=%9.3f B32=%8.3f loops16=%d loops32=%d"%(
        i, rms(pcm), rms(fl(o.r32(o16+0x48),160)), rms(fl(o.r32(o32+0x48),320)),
        rms(fl(o.r32(o16+0x34),160)), rms(fl(o.r32(o32+0x34),320)),
        rms(fl(o.r32(o16+0x38),320)), rms(fl(o.r32(o16+0x3c),320)),
        rms(fl(o.r32(o32+0x38),640)), rms(fl(o.r32(o32+0x3c),640)),
        counts['loop16'],counts['loop32']))
