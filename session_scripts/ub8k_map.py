"""Find the scratch->tap mapping: solve dll_out[i] = g2*S[a+i] + g1*S[b+i] + g0*S[c+i]
over the samples whose taps are all inside the history, then use the mapping to read the
DLL's tap values where they land inside the current sub-frame."""
import sys, struct, itertools
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
EXC=0x30012364
PCS={0x10009b6f:'clear',0x10009c0d:'ltp',0x10009f3e:'cb1',0x10009ff1:'cb2'}
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
scr={}; out=[]; ev=[]; last=[0]
def h(uc,a,s,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    last[0]=a
    if a==0x10009c0d:
        args=[o.r32(esp+4*k) for k in range(14)]
        out.append(('call',args))
    if a==0x10009c12: pass
def hw(uc,acc,addr,size,val,u):
    if EXC<=addr<EXC+640:
        ev.append((PCS.get(last[0],hex(last[0])),(addr-EXC)//4,
                   struct.unpack("<f",struct.pack("<I",val))[0]))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=EXC,end=EXC+640)
# read the scratch right after each call by capturing EIP transitions is unreliable;
# read it at the *next* call (the scratch is rewritten per call, so read before the call)
o.decode(ctx, blk)
# instead: emulate frame N with per-call scratch snapshots using a MEM_WRITE hook on the
# scratch to reconstruct its content at the moment of each LTP call is fragile; here we
# simply re-run the frame reading the scratch immediately after each call's return by
# stepping: use the call hook to snapshot, then read at the 'after' address.
print("calls:",len(out))
