import sys, json, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
dec=Full()
for i,(idx,blk) in enumerate(list(C.iter_blocks(d,info))[:2]):
    pcm=dec.decode_frame(blk,key=info['key'])
    print("frame %d mine:"%i, pcm[:20])
    print("frame %d ref :"%i, list(oracle[i][:20]))
    diff=[a-b for a,b in zip(pcm,oracle[i])]
    print("   rms diff=%.4f  max|d|=%d  nonzero mine=%d ref=%d"%(
        (sum(float(x)*x for x in diff)/640)**0.5, max(abs(x) for x in diff),
        sum(1 for x in pcm if x), sum(1 for x in oracle[i] if x)))
