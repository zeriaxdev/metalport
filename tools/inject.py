import sys, os, struct, bisect, collections, UnityPy, lz4.block
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metalsub import *
from UnityPy.enums import ShaderGpuProgramType as T
S = os.path.dirname(os.path.abspath(__file__))
def tname(v):
    try: return T(v).name.replace('kShaderGpuProgram', '')
    except Exception: return str(v)
BAD = ('DX11Geometry', 'DX11Hull', 'DX11Domain', 'DX11Compute')

def read_subs(tt, pi, blob):
    """Chunk 0 holds the table of (offset, length, chunk index); small shaders keep their data in chunk 0 itself."""
    offs, cls, dls = tt['offsets'][pi], tt['compressedLengths'][pi], tt['decompressedLengths'][pi]
    chunks = [lz4.block.decompress(blob[o:o+c], uncompressed_size=d) for o, c, d in zip(offs, cls, dls)]
    n = struct.unpack_from('<I', chunks[0], 0)[0]; subs = []
    for i in range(n):
        off, ln, seg = struct.unpack_from('<III', chunks[0], 4 + 12 * i)
        subs.append(chunks[seg][off:off + ln])
    return subs, len(chunks) > 1
def pack_chunks(subs, multi, limit=8 * 1024 * 1024):
    if not multi:
        head = 4 + 12 * len(subs); out = struct.pack('<I', len(subs)); off = head; body = b''
        for s in subs: out += struct.pack('<III', off, len(s), 0); off += len(s); body += s
        return [out + body]
    segs, cur, ents = [], bytearray(), []
    for s in subs:
        if cur and len(cur) + len(s) > limit: segs.append(bytes(cur)); cur = bytearray()
        ents.append((len(cur), len(s), len(segs) + 1)); cur += s
    segs.append(bytes(cur))
    table = struct.pack('<I', len(subs)) + b''.join(struct.pack('<III', *e) for e in ents)
    return [table] + segs

def patch_shader(tt, stats):
    plats = tt['platforms']
    if tt['m_ParsedForm']['m_Name'] in os.environ.get('SKIP_SHADER', '').split(','): stats['skip_by_env'] += 1; return False
    if 14 in plats or 4 not in plats: stats['skip_has_or_no_d3d'] += 1; return False
    pi = plats.index(4)
    blob = bytes(tt['compressedBlob'])
    subs, multi = read_subs(tt, pi, blob)
    types = [struct.unpack_from('<I', s, 4)[0] if len(s) >= 8 else -1 for s in subs]
    if any(tname(t).startswith(BAD) for t in types): stats['skip_unsupported_stage'] += 1; return False
    done = {}; new = []
    for i, s in enumerate(subs):
        if types[i] in VS_TYPES | PS_TYPES and b'DXBC' in s:
            p = f'{S}/cache/{dxbc_hash(s)}.metal'
            if os.path.exists(p):
                new.append(build_metal_sub(s, open(p, 'rb').read())); done[i] = True; continue
            stats['untranslated_variants'] += 1
        new.append(s)
    if not done: stats['skip_nothing_translated'] += 1; return False
    raws = pack_chunks(new, multi); comps = [lz4.block.compress(r, store_size=False, mode='high_compression', compression=9) for r in raws]
    new_offs, pos = [], len(blob)
    for c in comps: new_offs.append(pos); pos += len(c)
    P = tt['m_ParsedForm']['m_SubShaders']
    for ss in P:
        for ps in ss['m_Passes']:
            for st in ('progVertex', 'progFragment'):
                stg = ps[st]
                for g, grp in enumerate(stg['m_PlayerSubPrograms']):
                    add, addp = [], []
                    for e, pidx in zip(grp, stg['m_ParameterBlobIndices'][g]):
                        if e['m_GpuProgramType'] in VS_TYPES | PS_TYPES and done.get(e['m_BlobIndex']):
                            ne = dict(e); ne['m_GpuProgramType'] = METAL['VS'] if e['m_GpuProgramType'] in VS_TYPES else METAL['PS']
                            add.append(ne); addp.append(pidx)
                    grp.extend(add); stg['m_ParameterBlobIndices'][g].extend(addp); stats['entries_added'] += len(add)
    k = bisect.bisect(plats, 14)
    tt['platforms'].insert(k, 14); tt['offsets'].insert(k, new_offs); tt['compressedLengths'].insert(k, [len(c) for c in comps])
    tt['decompressedLengths'].insert(k, [len(r) for r in raws]); tt['stageCounts'].insert(k, 2)
    tt['compressedBlob'] = blob + b''.join(comps)
    stats['shaders_patched'] += 1; stats['subprograms_metal'] += len(done)
    return True

if __name__ == '__main__':
    data = sys.argv[1]; env = UnityPy.load(data); stats = collections.Counter(); modified = {}
    for obj in env.objects:
        if obj.type.name != 'Shader': continue
        try:
            tt = obj.read_typetree()
            if patch_shader(tt, stats):
                obj.save_typetree(tt); modified[id(obj.assets_file)] = obj.assets_file
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] < 4: print('ERR', obj.path_id, type(e).__name__, e)
    print(dict(stats), 'files to write:', len(modified))
    for f in modified.values():
        path = next(k for k, v in env.files.items() if v is f)
        print('writing', path); open(path, 'wb').write(f.save())
