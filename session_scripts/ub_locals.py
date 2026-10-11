import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
NF=38
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
for i in range(NF):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return ["%.4f"%x for x in struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n)))]
def r32(a): return o.r32(a)
seen={}
def hook(uc,addr,size,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    if addr==0x1000e623:
        vals={}
        for off in (0x18,0x1c,0x20,0x30,0x34,0x38,0x44,0x48):
            vals[off]=r32(esp+off)
        key=(esp,)
        if seen.get('n',0)<2:
            print("== at 0x1000e623 esp=%08x sf=%d"%(esp,vals[0x44]))
            for off in (0x18,0x1c,0x20,0x30,0x34,0x38,0x48):
                v=vals[off]
                print("   [esp+%02x]=%08x  %s  floats=%s"%(off,v, o.r32(v) if 0x30000000<=v<0x30020000 else '', fl(v,6) if 0x30000000<=v<0x30020000 else ''))
            print("   ebx=%08x esi=%08x edi=%08x ebp=%08x"%(uc.reg_read(UC_X86_REG_EBX),uc.reg_read(UC_X86_REG_ESI),uc.reg_read(UC_X86_REG_EDI),uc.reg_read(UC_X86_REG_EBP)))
            seen['n']=seen.get('n',0)+1
        else:
            seen['n']=seen.get('n',0)+1
    elif addr==0x1000e66d:
        if seen.get('m',0)<1:
            print("== codebook branch at 0x1000e66d esp=%08x esi=%08x"%(esp,uc.reg_read(UC_X86_REG_ESI)))
            for off in (0x18,0x1c,0x20,0x30,0x34,0x38,0x44,0x48):
                v=r32(esp+off)
                print("   [esp+%02x]=%08x %s"%(off,v, fl(v,6) if 0x30000000<=v<0x30020000 else ''))
            seen['m']=1
o.uc.hook_add(UC_HOOK_CODE,hook,begin=0x1000e600,end=0x1000e680)
o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
