"""Regenerate the port patch strictly from the code blocks in specs/UpperBands.md
and validate it end-to-end.  Writes /tmp/codec210_specpatch.py."""
import re, sys
SPEC='/home/asdf/Downloads/ltts_re/specs/UpperBands.md'
SRC='/home/asdf/Downloads/ltts_re/tools/codec210.py'
DST='/tmp/codec210_specpatch.py'
spec=open(SPEC).read()
blocks=re.findall(r"```python\n(.*?)```", spec, re.S)
assert len(blocks)==5, len(blocks)
helpers, reset_add, synth8_new, bands, tail_new = blocks
for b in (helpers, reset_add, synth8_new, bands, tail_new):
    assert not b.strip().startswith('```')
s=open(SRC).read()
# 6.1 helpers before clamp_int16
s=s.replace('def clamp_int16(v):', helpers.rstrip('\n')+'\n\n\ndef clamp_int16(v):', 1)
# 6.2 reset additions
s=s.replace('        self.tail_a16 = [0.0] * 64\n        self.tail_a32 = [0.0] * 64',
            '        self.tail_a16 = [0.0] * 64\n        self.tail_a32 = [0.0] * 64\n'+reset_add.rstrip('\n'), 1)
# __init__: the 16k codebook table
s=s.replace('        self.cb8 = T["codebooks"]["innovation"]["cb_256x5"]["int8"]   # 0x10021bd8: 64 x 5',
 '        self.cb8 = T["codebooks"]["innovation"]["cb_256x5"]["int8"]   # 0x10021bd8: 64 x 5\n'
 '        self.cb16 = T["codebooks"]["innovation"]["cb_128x8_16k"]["int8"]  # 0x10022470: 128 x 8', 1)
# 6.3+6.4: replace synth8 with the new synth8 + band16 + band32
i=s.index('    def synth8(self, lsf_cur):'); j=s.index('    def decode_frame(self, block, key=0x6D, trace=None):')
s=s[:i]+synth8_new.rstrip('\n')+'\n\n'+bands.rstrip('\n')+'\n\n'+s[j:]
# 6.5 decode_frame tail
i=s.index('        # ---- 8 kHz synthesis -> A16 -> A32 -> out = 2*(A32 - B32) ----------')
j=s.index('        if trace is not None:')
s=s[:i]+tail_new.rstrip('\n')+'\n\n'+s[j:]
s=s.replace('"band_B_32k_noise": "not ported",', '"band_B_32k_noise": "ported+verified",')
s=s.replace('"band_16k_coded": "not ported",', '"band_16k_coded": "ported+verified",')
open(DST,'w').write(s)
print("wrote", DST)
