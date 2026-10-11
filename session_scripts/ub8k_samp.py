"""Sample-level diff of the drifting 8 kHz excitation sub-frames."""
import sys, struct, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
class Probe(P.Codec210):
    def decode_frame(self, block, key=0x6D, trace=None):
        pcm=P.Codec210.decode_frame(self,block,key,trace)
        self.p_exc=list(self.buf[P.HIST:P.HIST+160])
        self.p_buf=list(self.buf)
        return pcm
dec=Probe()
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
o8=None
for i,(idx,blk) in enumerate(P.iter_blocks(*P.read_container(DEFAULT))):
    if i>120: break
    o8=o.r32(o.r32(o.r32(ctx+0x28)+4)+4)
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    pre=fl(0x30011ea0,160) if i==118 else None   # the excitation region before the frame
    pcm=o.decode(ctx, blk)
    m=dec.decode_frame(blk,key=0x6D)
    if i in (118,119,120):
        R=fl(o.r32(o8+0x3c),160)
        f=dec.parse_frame(blk)
        print("=== frame %d  g8=%d  sub8=%s"%(i,f["energy8"],[(a,b,c) for a,b,c,_ in f["sub8"]]))
        for sf in range(4):
            mine=dec.p_exc[40*sf:40*sf+40]; ref=R[40*sf:40*sf+40]
            n=len(mine); ma=sum(mine)/n; mb=sum(ref)/n
            num=sum((x-ma)*(y-mb) for x,y in zip(mine,ref))
            da=math.sqrt(sum((x-ma)**2 for x in mine)); db=math.sqrt(sum((y-mb)**2 for y in ref))
            c=num/(da*db) if da*db else 0.0
            print("  sf%d corr=%.5f rms %.4g/%.4g  mine[:6]=%s"%(sf,c,(ma**2+da**2/n)**.5,(mb**2+db**2/n)**.5,
                  ["%.6g"%x for x in mine[:6]]))
            print("                            ref [:6]=%s"%["%.6g"%x for x in ref[:6]])
            if c<0.999:
                print("       ratio mine/ref per sample[:8]=%s"%["%.4f"%(a/b if b else float('nan')) for a,b in zip(mine[:8],ref[:8])])
