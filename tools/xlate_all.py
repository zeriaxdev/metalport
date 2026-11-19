import sys, os, struct, hashlib, subprocess, collections, UnityPy, lz4.block
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxbc_rdef import add_rdef
from UnityPy.enums import ShaderGpuProgramType as T
S = os.path.dirname(os.path.abspath(__file__)); FLAGS = '0x1020081'
VS = {v for v in range(60) if 'DX11Vertex' in T(v).name} if False else None
def tname(v):
    try: return T(v).name.replace('kShaderGpuProgram', '')
    except Exception: return str(v)
def blobs(s, pi):
    # multi-chunk aware: chunk 0 holds the (offset, length, chunk) table
    offs, cls, dls = s.offsets[pi], s.compressedLengths[pi], s.decompressedLengths[pi]; cb = bytes(s.compressedBlob)
    chunks = [lz4.block.decompress(cb[o:o+c], uncompressed_size=d) for o, c, d in zip(offs, cls, dls)]
    n = struct.unpack_from('<I', chunks[0], 0)[0]; out = []
    for i in range(n):
        off, ln, seg = struct.unpack_from('<III', chunks[0], 4 + 12 * i); out.append(chunks[seg][off:off + ln])
    return out
def dxbc_of(sp):
    i = sp.find(b'DXBC'); return sp[i:i + struct.unpack_from('<I', sp, i + 24)[0]]
def work(h):
    dx = open(f'{S}/cache/{h}.dxbc', 'rb').read()
    open(f'{S}/cache/{h}.rdef.dxbc', 'wb').write(add_rdef(dx))
    r = subprocess.run([f'{S}/h2m', f'{S}/cache/{h}.rdef.dxbc', FLAGS], capture_output=True, timeout=60)
    if r.returncode == 0 and r.stdout:
        open(f'{S}/cache/{h}.metal', 'wb').write(r.stdout); return h, 'ok', ''
    return h, 'fail', f'rc={r.returncode} ' + r.stderr.decode('latin1')[:160].replace('\n', ' | ')
if __name__ == '__main__':
    env = UnityPy.load(sys.argv[1]); hs = {}; kinds = collections.Counter(); other = collections.Counter()
    for obj in env.objects:
        if obj.type.name != 'Shader': continue
        s = obj.read()
        if 4 not in list(s.platforms): continue
        for sp in blobs(s, list(s.platforms).index(4)):
            if b'DXBC' not in sp: continue
            ty = struct.unpack_from('<I', sp, 4)[0]; kinds[tname(ty)] += 1
            dx = dxbc_of(sp); h = hashlib.sha1(dx).hexdigest()[:16]
            if h not in hs: open(f'{S}/cache/{h}.dxbc', 'wb').write(dx); hs[h] = 1
    print('subprogram kinds:', dict(kinds)); print('unique DXBC:', len(hs), flush=True)
    res = collections.Counter(); fails = collections.Counter()
    with Pool(10) as p:
        for h, st, msg in p.imap_unordered(work, list(hs), chunksize=8):
            res[st] += 1
            if st == 'fail': fails[msg[:110]] += 1
    print('result:', dict(res)); print('top failures:'); [print('  ', n, m) for m, n in fails.most_common(8)]
