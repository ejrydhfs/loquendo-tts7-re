"""Identify the scratch->tap mapping: for a lag>=41 sub-frame all tap values are known
(history), so we can locate the three windows inside the DLL's 120-float scratch."""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
N=118
dec=P.Codec210()
snap=[]
for i in range(N+1):
    dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D); snap.append(list(dec.buf))
pre=snap[N-1]
f=dec.parse_frame(d[150+N*110:150+(N+1)*110],0x6D)
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i in range(N): o.decode(ctx, d[150+i*110:150+(i+1)*110])
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
snaps=[]; pend=None
def h(uc,a,s,u):
    global pend
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x10009c0d: pend=[o.r32(esp+4*k) for k in range(14)]
    elif a==0x10009c12 and pend:
        snaps.append(fl(pend[9],120)); pend=None
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, d[150+N*110:150+(N+1)*110])
b=list(pre); b[0:P.HIST]=b[160:160+P.HIST]
for sf,(S) in enumerate(snaps[:4]):
    lag=f["sub8"][sf][0]+17; p=P.HIST+40*sf; w0=p-(lag+1)
    # expected tap values (the history part is exact; only valid when all taps are history)
    W0=[b[w0+i] for i in range(40)]
    W1=[b[w0+1+i] for i in range(40)]
    W2=[b[w0+2+i] for i in range(40)]
    def locate(W):
        best=None
        for a in range(0,81):
            err=max(abs(S[a+i]-W[i]) for i in range(40))
            if best is None or err<best[1]: best=(a,err)
        return best
    print("sf%d lag=%3d: W0 at scratch %s ; W1 at %s ; W2 at %s"%(
        sf,lag,locate(W0),locate(W1),locate(W2)))
    print("    S[0:8]=",["%.5g"%x for x in S[:8]])
    print("    W0[:8]=",["%.5g"%x for x in W0[:8]])
