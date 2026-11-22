import sys, os, struct, bisect, collections, json, UnityPy, lz4.block
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metalsub import *
import cbfix
import re
from compute_shader.unityblob import VERSION, parse_params, write_params
from metal_check import require_valid
from compute_support import patch_compute
from UnityPy.enums import ShaderGpuProgramType as T
S = os.path.dirname(os.path.abspath(__file__))
def tname(v):
    try: return T(v).name.replace('kShaderGpuProgram', '')
    except Exception: return str(v)
BAD = ('DX11Geometry', 'DX11Hull', 'DX11Domain', 'DX11Compute')

def cached_msl(sub):
    p = f'{S}/cache/{dxbc_hash(sub)}'
    if os.path.exists(p + '.translation.json'):
        with open(p + '.translation.json') as stream:
            if json.load(stream).get('failed'): return None
    return open(p + '.metal', 'rb').read() if os.path.exists(p + '.metal') else None

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

# HLSLcc allocates Metal slots independently for each translated program.
METAL_SLOT = re.compile(rb"\b(cb|buf|tex|sampler_s)(\d+)\s*\[\[\s*(buffer|texture|sampler)\s*\(\s*(\d+)\s*\)")
BINDING_KIND = {
    (b"tex", b"texture"): 0,
    (b"cb", b"buffer"): 1,
    (b"buf", b"buffer"): 2,
    (b"sampler_s", b"sampler"): 4,
}


def remap_metal_params(data, msl):
    if data[:4] != struct.pack("<I", VERSION):
        return data
    slots = {
        (BINDING_KIND[prefix, space], int(source)): int(target)
        for prefix, source, space, target in METAL_SLOT.findall(msl)
        if (prefix, space) in BINDING_KIND and source != target
    }
    if not slots:
        return data
    params = parse_params(data)
    changed = False
    for binding in params["bindings"]:
        kind, index = binding["kind"], binding["index"]
        new_index = slots.get((kind, index), index)
        binding["index"] = new_index
        changed |= new_index != index
        if kind == 0:
            sampler = binding["extra"]
            binding["extra"] = slots.get((4, sampler), sampler)
            changed |= binding["extra"] != sampler
    return write_params(params) if changed else data


def patch_shader(tt, stats):
    plats = tt['platforms']
    if tt['m_ParsedForm']['m_Name'] in os.environ.get('SKIP_SHADER', '').split(','): stats['skip_by_env'] += 1; return False
    if 14 in plats or 4 not in plats: stats['skip_has_or_no_d3d'] += 1; return False
    pi = plats.index(4)
    blob = bytes(tt['compressedBlob'])
    subs, multi = read_subs(tt, pi, blob)
    types = [struct.unpack_from('<I', s, 4)[0] if len(s) >= 8 else -1 for s in subs]
    if any(tname(t).startswith(BAD) for t in types): stats['skip_unsupported_stage'] += 1; return False
    mtl = {}
    for i, s in enumerate(subs):
        if types[i] in VS_TYPES | PS_TYPES and b'DXBC' in s:
            source = cached_msl(s)
            if source is not None: mtl[i] = source
            else: stats['untranslated_variants'] += 1
    required = sum(t in VS_TYPES | PS_TYPES for t in types)
    if len(mtl) != required:
        if os.environ.get('ALLOW_PARTIAL_SHADER') != '1':
            stats['skip_incomplete_shader'] += 1
            return False
        stats['partial_shaders'] += 1
        stats['omitted_graphics_variants'] += required - len(mtl)
    users = collections.defaultdict(list); inpass = {}     # Unity 2020.2+: parameter blob index -> translated programs that use it
    for ss in tt['m_ParsedForm']['m_SubShaders']:
        for ps in ss['m_Passes']:
            for st in ('progVertex', 'progFragment'):
                stg = ps.get(st) or {}
                for g, grp in enumerate(stg.get('m_PlayerSubPrograms', [])):
                    for e, pidx in zip(grp, stg['m_ParameterBlobIndices'][g]):
                        if e['m_BlobIndex'] in mtl and e['m_BlobIndex'] not in users[pidx]: users[pidx].append(e['m_BlobIndex'])
                        inpass.setdefault(id(ps), set()).add(pidx)
    allocs = {}
    for pids in inpass.values():                           # one free-register allocator per pass (vertex + fragment share $Globals)
        al = cbfix.pass_alloc([subs[q] for q in pids])
        for q in pids: allocs.setdefault(q, al)
    params = {}
    for pidx, progs in users.items():                      # float3 clobber fix (cbfix.py), all users of a table or none
        pl = cbfix.plan(subs[pidx], allocs.get(pidx))
        if not pl: continue
        fixed = {i: cbfix.patch_msl(mtl[i], pl[1], pl[2]) for i in progs}
        if any(v is None for v in fixed.values()): stats['cbfix_refused'] += 1; continue
        mtl.update(fixed); params[pidx] = pl[0]; stats['cbfix_scalars_moved'] += len(pl[1])
    require_valid(mtl.values())  # Check final MSL after cbfix, before changing the shader.
    done = {}; new = []
    for i, s in enumerate(subs):
        if i in mtl: new.append(build_metal_sub(s, mtl[i])); done[i] = True
        else: new.append(params.get(i, s))
    if not done: stats['skip_nothing_translated'] += 1; return False
    metal_params = {}
    for pidx, programs in users.items():
        for program in programs:
            data = remap_metal_params(new[pidx], mtl[program])
            if data != new[pidx]:
                metal_params[pidx, program] = len(new)
                new.append(data)
    stats['metal_parameter_tables_rebound'] += len(metal_params)
    raws = pack_chunks(new, multi); comps = [lz4.block.compress(r, store_size=False, mode='high_compression', compression=9) for r in raws]
    new_offs, pos = [], len(blob)
    for c in comps: new_offs.append(pos); pos += len(c)
    P = tt['m_ParsedForm']['m_SubShaders']
    for ss in P:
        for ps in ss['m_Passes']:
            for st in ('progVertex', 'progFragment'):
                stg = ps[st]
                if 'm_PlayerSubPrograms' not in stg:      # Unity 2019.x: one flat list, parameters inline, no blob-index lists
                    grp = stg['m_SubPrograms']; add = []
                    for e in grp:
                        if e['m_GpuProgramType'] in VS_TYPES | PS_TYPES and done.get(e['m_BlobIndex']):
                            ne = dict(e); ne['m_GpuProgramType'] = METAL['VS'] if e['m_GpuProgramType'] in VS_TYPES else METAL['PS']; add.append(ne)
                    grp.extend(add); stats['entries_added'] += len(add)
                    continue
                for g, grp in enumerate(stg['m_PlayerSubPrograms']):
                    add, addp = [], []
                    for e, pidx in zip(grp, stg['m_ParameterBlobIndices'][g]):
                        if e['m_GpuProgramType'] in VS_TYPES | PS_TYPES and done.get(e['m_BlobIndex']):
                            ne = dict(e); ne['m_GpuProgramType'] = METAL['VS'] if e['m_GpuProgramType'] in VS_TYPES else METAL['PS']
                            add.append(ne); addp.append(metal_params.get((pidx, e['m_BlobIndex']), pidx))
                    grp.extend(add); stg['m_ParameterBlobIndices'][g].extend(addp); stats['entries_added'] += len(add)
    k = bisect.bisect(plats, 14)
    tt['platforms'].insert(k, 14); tt['offsets'].insert(k, new_offs); tt['compressedLengths'].insert(k, [len(c) for c in comps])
    tt['decompressedLengths'].insert(k, [len(r) for r in raws])
    if 'stageCounts' in tt: tt['stageCounts'].insert(k, 2)      # absent in Unity 2019.x
    tt['compressedBlob'] = blob + b''.join(comps)
    stats['shaders_patched'] += 1; stats['subprograms_metal'] += len(done)
    return True

def refix_metal(tt, stats):
    """Apply the cbfix float3 fix to a shader that already got Metal programs without it (Unity 2020.2+ layout).  Rebuilds the affected
    Metal programs from the D3D ones + cached MSL and replaces the platform-14 blob; D3D data untouched."""
    plats = tt['platforms']
    if 14 not in plats or 4 not in plats: return False
    blob = bytes(tt['compressedBlob']); k = plats.index(14)
    subs4, _ = read_subs(tt, plats.index(4), blob); subs14, multi = read_subs(tt, k, blob)
    if len(subs4) != len(subs14): stats['refix_layout_mismatch'] += 1; return False
    users = collections.defaultdict(list); inpass = {}
    for ss in tt['m_ParsedForm']['m_SubShaders']:
        for ps in ss['m_Passes']:
            for st in ('progVertex', 'progFragment'):
                stg = ps.get(st) or {}
                for g, grp in enumerate(stg.get('m_PlayerSubPrograms', [])):
                    for e, pidx in zip(grp, stg['m_ParameterBlobIndices'][g]):
                        i = e['m_BlobIndex']
                        if e['m_GpuProgramType'] in METAL.values():
                            if i not in users[pidx]: users[pidx].append(i)
                            inpass.setdefault(id(ps), set()).add(pidx)
    allocs = {}
    for pids in inpass.values():
        al = cbfix.pass_alloc([subs14[q] for q in pids])
        for q in pids: allocs.setdefault(q, al)
    new = list(subs14); changed = False
    for pidx, progs in users.items():
        pl = cbfix.plan(subs14[pidx], allocs.get(pidx))
        if not pl: continue
        fixed = {}
        for i in progs:
            source = cached_msl(subs4[i]) if b'DXBC' in subs4[i] else None
            if source is None: fixed = None; break
            fixed[i] = cbfix.patch_msl(source, pl[1], pl[2])
            if fixed[i] is None: fixed = None; break
        if not fixed: stats['cbfix_refused'] += 1; continue
        require_valid(fixed.values())
        for i, msl in fixed.items(): new[i] = build_metal_sub(subs4[i], msl)
        new[pidx] = pl[0]; changed = True; stats['cbfix_scalars_moved'] += len(pl[1])
    if not changed: return False
    raws = pack_chunks(new, multi); comps = [lz4.block.compress(r, store_size=False, mode='high_compression', compression=9) for r in raws]
    offs, pos = [], len(blob)
    for c in comps: offs.append(pos); pos += len(c)
    tt['offsets'][k] = offs; tt['compressedLengths'][k] = [len(c) for c in comps]; tt['decompressedLengths'][k] = [len(r) for r in raws]
    tt['compressedBlob'] = blob + b''.join(comps)           # ponytail: old Metal chunk stays as dead bytes; a full re-port drops it
    stats['shaders_refixed'] += 1
    return True

if __name__ == '__main__':
    data = sys.argv[1]; env = UnityPy.load(data); stats = collections.Counter(); modified = {}
    for obj in env.objects:
        if obj.type.name not in ('Shader', 'ComputeShader'): continue
        try:
            tt = obj.read_typetree()
            if (patch_compute if obj.type.name == 'ComputeShader' else patch_shader)(tt, stats):
                obj.save_typetree(tt); modified[id(obj.assets_file)] = obj.assets_file
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] < 4: print('ERR', obj.path_id, type(e).__name__, e)
    print(dict(stats), 'files to write:', len(modified))
    for f in modified.values():
        path = next(k for k, v in env.files.items() if v is f)
        print('writing', path); open(path, 'wb').write(f.save())
    if stats['errors'] or stats['compute_failed'] or stats['partial_shaders'] or stats['skip_incomplete_shader'] or stats['skip_unsupported_stage']: sys.exit(2)
