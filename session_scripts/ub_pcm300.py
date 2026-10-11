import sys, struct, json
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
allpcm=[]
for i in range(300):
    allpcm.append(o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE]))
json.dump(allpcm, open('/tmp/oracle_pcm_0_299.json','w'))
print("ok", len(allpcm))
