"""Compare the DLL's 120-float tap scratch with the port's flat window buf[w0:w0+120]
sample by sample => reveals the layout and the DLL's tap values in the current sub-frame."""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
N=int(sys.argv[1]) if len(sys.argv)>1 else 118
dec=P.Codec210()
for i in range(N):
    dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D)
blk=d[150+N*110:150+(N+1)*110]
f=dec.parse_frame(blk,0x6D)
pre=list(dec.buf)
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i in range(N):
    o.decode(ctx, d[150+i*110:150+(i+1)*110])
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
snaps=[]; pend=None
def h(uc,a,s,u):
    global pend
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x10009c0d:
        pend=[o.r32(esp+4*k) for k in range(14)]
    elif a==0x10009c12 and pend:
        snaps.append((pend, fl(pend[9],120)))
        pend=None
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.decode(ctx, blk)

buf=list(pre); buf[0:P.HIST]=buf[160:160+P.HIST]
for sf,(args,S) in enumerate(snaps[:4]):
    lag=f["sub8"][sf][0]+17; p=P.HIST+40*sf; w0=p-(lag+1)
    flat=[buf[w0+k] if 0<=w0+k<len(buf) else 0.0 for k in range(120)]
    agree=[k for k in range(120) if abs(S[k]-flat[k])<=1e-4*max(1.0,abs(S[k]))]
    print("sf%d lag=%d: scratch==flat for %d/120 slots; first mismatch k=%s"%(
        sf,lag,len(agree),next((k for k in range(120) if k not in agree),None)))
    if len(agree)<120:
        k0=next(k for k in range(120) if k not in agree)
        print("   last agreeing k=%d (position p%+d)  first mismatch k=%d (position p%+d)"%(
            k0-1,(w0+k0-1)-p,k0,(w0+k0)-p))
        print("   dll S[k0-3..k0+5] =",["%.6g"%x for x in S[k0-3:k0+6]])
        print("   flat     [..]     =",["%.6g"%x for x in flat[k0-3:k0+6]])
        print("   pre-clear buf at those positions =",
              ["%.6g"%buf[w0+kk] for kk in range(k0-3,k0+6)])
