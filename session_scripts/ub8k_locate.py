"""Locate the DLL's tap value V(0)=92.2064 (solved for frame 118 sf1) in the port's
buffer/dumps to identify which memory the tap copy actually read."""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
N=118
dec=P.Codec210()
snap=[]
for i in range(N+1):
    dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D)
    snap.append(list(dec.buf))
pre=snap[N-1]           # state after frame 117 (before frame 118)
post=snap[N]            # state after frame 118
targets={'V0':92.20640,'V1':15.44999,'V2':244.00425,'V3':390.37333}
for name,t in targets.items():
    hits=[]
    for lbl,b in (('pre',pre),('post',post),('exc117',snap[N-1][P.HIST:P.HIST+160]),
                  ('exc118',snap[N][P.HIST:P.HIST+160])):
        for k,v in enumerate(b):
            if abs(v-t)<=1e-3*max(1.0,abs(t)): hits.append((lbl,k,v))
    print(name,"%9.5f"%t,"hits:",hits[:6])
print()
print("pre[84:96] =",["%.5g"%x for x in pre[84:96]])
print("post[185:205]=",["%.5g"%x for x in post[P.HIST+40:P.HIST+60]])
