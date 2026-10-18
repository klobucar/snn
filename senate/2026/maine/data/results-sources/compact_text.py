from research import *
# Lossless compression only. Original entities already live in objects/*.gz.
count=0
for directory in ['requests','extracted']:
 for f in (ROOT/directory).glob('*.txt'):
  if f.stat().st_size>250000:
   target=f.with_suffix('.txt.gz');target.write_bytes(gzip.compress(f.read_bytes(),mtime=0));f.unlink();count+=1
print('large derived text files compressed',count)
