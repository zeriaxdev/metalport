#!/usr/bin/env python3
"""Read-only: show where a Shader's shared parameters (m_CommonParameters) end up per platform.

Unity 2020.1+ stores parameters that all subprograms of a program share once, in the parsed form's
m_CommonParameters, and leaves them out of the per-subprogram parameter entries. This prints, per
pass and stage, which common constant-buffer members exist and whether the parameter entry used by
the D3D11 and Metal subprograms lists them itself. Nothing is written.

    python3 tools/dump_common_params.py <serialized file> [--shader Lut2DBaker]
"""
import argparse
import os
import sys

import lz4.block
import UnityPy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_shader.unityblob import entries, parse_params  # noqa: E402

D3D11, METAL = 4, 14
STAGE_TYPES = {'progVertex': {4: (15, 'D3D11 VS'), 14: (23, 'Metal VS')},
               'progFragment': {4: (17, 'D3D11 PS'), 14: (24, 'Metal PS')}}


def platform_entries(tree, platform):
    if platform not in tree['platforms']:
        return None
    i = tree['platforms'].index(platform)
    blob = bytes(tree['compressedBlob'])
    segs = [lz4.block.decompress(blob[o:o + c], uncompressed_size=d)
            for o, c, d in zip(tree['offsets'][i], tree['compressedLengths'][i], tree['decompressedLengths'][i])]
    return entries(segs)


def common_members(cp, names):
    """{constant buffer name: [(member, offset)]} for the shared parameters."""
    out = {}
    for cb in cp.get('m_ConstantBuffers') or []:
        out[names.get(cb['m_NameIndex'], '?')] = sorted(
            [(names.get(v['m_NameIndex'], '?'), v['m_Index']) for v in cb['m_VectorParams']] +
            [(names.get(m['m_NameIndex'], '?'), m['m_Index']) for m in cb['m_MatrixParams']], key=lambda x: x[1])
    return out


def entry_members(raw):
    try:
        d = parse_params(raw)
    except Exception as e:  # layout of another Unity version
        return None, 'unparsable: %s' % e
    return {g['name']: {p['name'] for p in g['params']} for g in d['groups']}, None


def report(name, tree):
    plats = {p: platform_entries(tree, p) for p in (D3D11, METAL)}
    print('== %s  platforms=%s' % (name, tree['platforms']))
    for si, ss in enumerate(tree['m_ParsedForm']['m_SubShaders']):
        for pi, ps in enumerate(ss['m_Passes']):
            names = {i: n for n, i in ps.get('m_NameIndices') or []}
            for stage, types in STAGE_TYPES.items():
                prog = ps.get(stage) or {}
                common = common_members(prog.get('m_CommonParameters') or {}, names)
                print('-- subshader %d pass %d %s: common=%s' % (
                    si, pi, stage, {k: ['%s@%d' % m for m in v] for k, v in common.items()} or 'none'))
                for g, grp in enumerate(prog.get('m_PlayerSubPrograms') or []):
                    pbis = (prog.get('m_ParameterBlobIndices') or [[]] * (g + 1))[g]
                    for sp, pbi in zip(grp, pbis):
                        for plat, (gpu, label) in types.items():
                            if sp['m_GpuProgramType'] != gpu or plats[plat] is None:
                                continue
                            if pbi >= len(plats[plat]):
                                print('   %s blob %d: parameter entry %d out of range' % (label, sp['m_BlobIndex'], pbi))
                                continue
                            have, err = entry_members(plats[plat][pbi])
                            if err:
                                print('   %s blob %d: %s' % (label, sp['m_BlobIndex'], err))
                                continue
                            missing = {cb: [m for m, _ in mem if m not in have.get(cb, ())] for cb, mem in common.items()}
                            missing = {k: v for k, v in missing.items() if v}
                            print('   %s blob %d param entry %d: own CBs=%s, common members missing from entry=%s' % (
                                label, sp['m_BlobIndex'], pbi,
                                {k: len(v) for k, v in have.items()}, {k: len(v) for k, v in missing.items()} or 'none'))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--shader', default='', help='substring of the shader name')
    args = ap.parse_args(argv)
    env = UnityPy.load(args.file)
    found = 0
    for o in env.objects:
        if o.type.name != 'Shader':
            continue
        tree = o.read_typetree()
        name = tree['m_ParsedForm']['m_Name']
        if args.shader in name:
            found += 1
            report(name, tree)
    if not found:
        print('no matching Shader object', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
