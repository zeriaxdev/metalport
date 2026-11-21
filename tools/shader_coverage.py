"""Shared loose-file/UnityFS inventory for inspection, translation and app patching."""
import collections
import hashlib
import json
import re
import struct
from pathlib import Path

import UnityPy
from inject import BAD, read_subs, tname
from metalsub import VS_TYPES, PS_TYPES
from metal_check import atomic_write
from compute_support import info as compute_info


def asset_files(root):
    root = Path(root).resolve()
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        raise ValueError(f'Data path does not exist: {root}')
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix in ('.assets', '.bundle', '.unity3d', '.assetbundle') or re.fullmatch(r'level\d+|globalgamemanagers|unity_builtin_extra|unity default resources|unity_default_resources', path.name):
            yield path


def scan(root, skip=(), audit=False):
    report = {'phase': 'output' if audit else 'source', 'root': str(Path(root).resolve()), 'files': [], 'issues': [], 'counts': {}}
    jobs = {}
    counts = collections.Counter()
    for path in asset_files(root):
        item = {'path': str(path), 'shaders': []}
        report['files'].append(item)
        try:
            env = UnityPy.load(str(path))
            for obj in env.objects:
                kind = obj.type.name
                if kind not in ('Shader', 'ComputeShader'):
                    continue
                counts[kind] += 1
                tree = obj.read_typetree()
                name = tree.get('m_Name') or tree.get('m_ParsedForm', {}).get('m_Name') or str(obj.path_id)
                row = {'path_id': obj.path_id, 'kind': kind, 'name': name, 'programs': [], 'issues': []}
                item['shaders'].append(row)
                def issue(code, detail):
                    entry = {'file': str(path), 'path_id': obj.path_id, 'name': name, 'code': code, 'detail': detail}
                    row['issues'].append(entry)
                    report['issues'].append(entry)
                if name in skip:
                    issue('excluded_by_name', 'Explicit --skip-shader exclusion; rendering fallback is not verified')
                    continue
                if kind == 'ComputeShader':
                    try:
                        row['compute'] = compute_info(tree)
                        if row['compute']['metal']:
                            counts['ComputeWithMetal'] += 1
                        elif audit:
                            issue('missing_metal_compute', 'Compute shader has no Metal renderer')
                    except (ValueError, KeyError, TypeError, IndexError) as error:
                        issue('unsupported_compute', str(error))
                    continue
                platforms = tree['platforms']
                row['platforms'] = list(platforms)
                if 4 in platforms:
                    subs, _ = read_subs(tree, platforms.index(4), bytes(tree['compressedBlob']))
                    stages = set()
                    for sub in subs:
                        ty = struct.unpack_from('<I', sub, 4)[0] if len(sub) >= 8 else -1
                        stage = tname(ty)
                        if stage.startswith(BAD):
                            stages.add(stage)
                        if ty not in VS_TYPES | PS_TYPES:
                            continue
                        offset = sub.find(b'DXBC')
                        if offset < 0:
                            issue('missing_dxbc', f'{stage} has no DXBC payload')
                            continue
                        length = struct.unpack_from('<I', sub, offset + 24)[0]
                        dxbc = sub[offset:offset + length]
                        if length < 32 or len(dxbc) != length:
                            raise ValueError('Truncated DXBC payload')
                        digest = hashlib.sha1(dxbc).hexdigest()[:16]
                        row['programs'].append({'hash': digest, 'stage': stage})
                        if not audit and 14 not in platforms:
                            if digest in jobs and jobs[digest] != dxbc:
                                raise ValueError('DXBC cache key collision')
                            jobs[digest] = dxbc
                    if stages:
                        issue('unsupported_stage', ', '.join(sorted(stages)))
                elif 14 not in platforms:
                    issue('no_supported_source', 'Neither D3D11 nor Metal shader data present')
                if audit and 14 not in platforms:
                    issue('missing_metal', 'Shader has no Metal platform')
                if 14 in platforms:
                    counts['ShaderWithMetal'] += 1
                    metal, _ = read_subs(tree, platforms.index(14), bytes(tree['compressedBlob']))
                    if any(len(sub) >= 8 and b'DXBC' in sub and struct.unpack_from('<I', sub, 4)[0] in VS_TYPES | PS_TYPES for sub in metal):
                        issue('partial_metal', 'D3D graphics programs remain in the Metal platform')
        except Exception as error:
            report['issues'].append({'file': str(path), 'code': 'read_error', 'detail': f'{type(error).__name__}: {error}'})
    report['counts'] = dict(counts)
    if not counts['Shader'] and not counts['ComputeShader']:
        report['issues'].append({'code': 'no_shaders', 'detail': 'No shader objects found'})
    report['unique_programs'] = len({p['hash'] for item in report['files'] for shader in item['shaders'] for p in shader['programs']})
    return report, jobs


def finish(report, destination):
    report['complete'] = not report['issues']
    atomic_write(Path(destination), (json.dumps(report, indent=2) + '\n').encode())
    print(f"Shader coverage: {report['counts']}; {len(report['issues'])} issue(s). Report: {destination}", flush=True)
    for issue in report['issues'][:5]:
        print(f"  {issue['code']}: {issue.get('name', issue.get('file', ''))}: {issue['detail']}", flush=True)
    return report['complete']
