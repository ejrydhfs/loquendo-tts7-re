import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
def rms(v): return (sum(x*x for x in v)/len(v))**0.5
n=[0]
def h(uc,a,s,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x10002ec0:
        ret=o.r32(esp); p=o.r32(esp+4); cnt=o.r32(esp+8)
        n[0]+=1
        print("  cp%08x EC0 p=%08x n=%d ret=%08x"%(0,p,cnt,ret))
        try:
            print("      rms=%.6g first=%s"%(rms(fl(p,cnt)),["%.6g"%x for x in fl(p,4)]))
        except Exception as e: print("      (unreadable)",e)
    if False:
        print("  [%08x] esp=%08x"%(a,esp))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002ec0,end=0x10002ec1)

o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e65b,end=0x1000e65c)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
print("calls:",n[0])
print("o8[+48]=%08x rms20 per sf: %s"%(o.r32(o8+0x48), ["%.6g"%rms(fl(o.r32(o8+0x48)+20*k,20)) for k in range(8)]))
print("o8[+3c]=%08x rms40 per sf: %s"%(o.r32(o8+0x3c), ["%.6g"%rms(fl(o.r32(o8+0x3c)+40*k,40)) for k in range(4)]))
print("o8[+30]=%08x rms40 per sf: %s"%(o.r32(o8+0x30), ["%.6g"%rms(fl(o.r32(o8+0x30)+40*k,40)) for k in range(4)]))
print("o8[+40]=%08x rms40 per sf: %s"%(o.r32(o8+0x40), ["%.6g"%rms(fl(o.r32(o8+0x40)+40*k,40)) for k in range(4)]))
print("o8[+44]=%08x rms40 per sf: %s"%(o.r32(o8+0x44), ["%.6g"%rms(fl(o.r32(o8+0x44)+40*k,40)) for k in range(4)]))
print("const 0x10022120 =", struct.unpack("<d", bytes(o.uc.mem_read(0x10022120,8)))[0])
