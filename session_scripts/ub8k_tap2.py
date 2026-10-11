"""Find the real LTP tap-copy scratch of FUN_10006bb0 and read what it copies."""
import sys, struct, collections
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
def analyse(N):
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N):
        o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    ev=[]; last=[0]
    def hc(uc,a,s,u): last[0]=a
    def hw(uc,acc,addr,size,val,u):
        if 0x30000000<=addr<0x30040000:
            ev.append((last[0],addr,size,struct.unpack("<f",struct.pack("<I",val))[0]))
    o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
    o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=0x30000000,end=0x30040000)
    o.decode(ctx, d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE])
    c=collections.Counter(p for p,_,_,_ in ev)
    print("=== frame %d: distinct write pcs=%d"%(N,len(c)))
    for p,n in c.most_common(14):
        addrs=sorted(set(a for pp,a,_,_ in ev if pp==p))
        print("   %08x x%-5d  first=%08x last=%08x size=%s"%(p,n,addrs[0],addrs[-1],
              sorted(set(s for pp,_,s,_ in ev if pp==p))))
    # all writers inside FUN_10006bb0 (0x10006b?0..0x10007000)
    ins=[(p,a,s,v) for p,a,s,v in ev if 0x10006b00<=p<0x10007000]
    print("   writers in FUN_10006bb0: %s"%collections.Counter(p for p,_,_,_ in ins))
    if ins:
        print("   their addresses: %s"%sorted(set(hex(a) for _,a,_,_ in ins)))
        print("   first 8 values:",[("%08x"%a,"%.6g"%v) for _,a,_,v in ins[:8]])
analyse(int(sys.argv[1]) if len(sys.argv)>1 else 118)
