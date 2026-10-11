"""Apply the lag-periodic ring LTP fix to a copy of tools/codec210.py and measure e2e."""
import re
src='/home/asdf/Downloads/ltts_re/tools/codec210.py'
dst='/tmp/codec210_ring.py'
s=open(src).read()
i=s.index('    def ltp(self, p, lag, idx):')
j=s.index('    def codebook(self, idxs, base):')
new = '''    def ltp(self, p, lag, idx):
        """FUN_10006bb0 — 8 kHz adaptive codebook.

        The DLL's tap windows are a *cyclic* read of the `lag` samples that end just before
        the current sub-block: for tap index k (relative to w0 = p-(lag+1)) the source is
        buf[w0+k] while k <= lag, else buf[w0+1+((k-1) % lag)] (measured from the DLL's own
        120-float tap scratch; equivalently the DLL never reads the current sub-block, it
        wraps back onto the previous `lag` samples).  For lag >= 41 the ring never wraps
        inside the 42 taps used, so this is the plain 3-tap predictor.
        """
        tbl = self.pitch_tbl
        g = [tbl[idx * 3 + k] / 64.0 + 0.5 for k in range(3)]
        w0 = p - (lag + 1)
        buf = self.buf
        out = []
        for i in range(40):
            v = 0.0
            for j, coef in ((i, g[2]), (i + 1, g[1]), (i + 2, g[0])):
                if j > lag:
                    j = 1 + ((j - 1) % lag)
                a = w0 + j
                v += coef * (buf[a] if a >= 0 else 0.0)
            out.append(_f32(v))
        return out

'''
s = s[:i] + new + s[j:]
open(dst,'w').write(s)
print("wrote", dst)
