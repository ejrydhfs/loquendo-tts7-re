import sys, struct, collections
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
def frame_addrs(N):
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N):
        o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    hits=set()
    def h(uc,a,s,u): hits.add(a)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
    o.decode(ctx, d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE])
    return sorted(hits)
def ranges(addrs, lo, hi, gap=0x40):
    out=[]; cur=None
    for a in addrs:
        if not (lo<=a<hi): continue
        if cur and a-cur[1]<=gap: cur[1]=a
        else:
            if cur: out.append(cur)
            cur=[a,a]
    if cur: out.append(cur)
    return out
for N in (38,119,120,121,170):
    A=frame_addrs(N)
    rs=ranges(A,0x10009520,0x1000a400)
    print("frame %3d: %d addrs total; FUN_10009520 spans: %s"%(N,len(A),
        " ".join("%x-%x"%tuple(r) for r in rs)))
