"""Versioned Unity 2021/2022 compute conversion with reflected Metal bindings."""
import collections
import copy
import fcntl
import hashlib
import json
import os
import platform
from pathlib import Path
import struct
import subprocess
import tempfile

from compute_shader import compute as C, metal
from metal_check import atomic_write, require_valid

HERE = Path(__file__).resolve().parent
CACHE = HERE / 'cache' / 'compute'
COMMIT = '3ea1fcd6bd0ac445bc078de0bf32f0950188577b'


class ComputeToolUnavailable(RuntimeError):
    pass


def kernel_variants(kernel):
    """Yield (layout, index, descriptor), preserving the original keyword/index tables."""
    if 'variantMap' in kernel and 'uniqueVariants' not in kernel:
        for i, pair in enumerate(kernel['variantMap']):
            if len(pair) != 2 or not isinstance(pair[1], dict):
                raise ValueError('Invalid Unity 2021 variantMap')
            yield 'variantMap', i, pair[1]
    elif 'uniqueVariants' in kernel and 'variantIndices' in kernel and 'variantMap' not in kernel:
        variants = kernel['uniqueVariants']
        for pair in kernel['variantIndices']:
            if len(pair) != 2 or type(pair[1]) is not int or not 0 <= pair[1] < len(variants):
                raise ValueError('Invalid Unity 2022 variantIndices')
        for i, variant in enumerate(variants):
            yield 'uniqueVariants', i, variant
    else:
        raise ValueError('Unsupported or ambiguous compute kernel serialization')


def descriptors(tree, renderer=C.D3D11_RENDERER):
    for vi, variant in enumerate(tree.get('variants', [])):
        if variant['targetRenderer'] != renderer:
            continue
        for ki, kernel in enumerate(variant['kernels']):
            records = list(kernel_variants(kernel))
            if not records:
                raise ValueError('Compute kernel has no variants: ' + kernel['name'])
            for layout, index, kv in records:
                group = kv['threadGroupSize']
                if len(group) != 3 or any(type(v) is not int or not 0 < v <= 65535 for v in group):
                    raise ValueError('Invalid compute thread group size')
                indices, bindings = kv['cbVariantIndices'], kv['cbs']
                if len(indices) != len(bindings) or any(type(v) is not int or not 0 <= v < len(variant['constantBuffers']) for v in indices):
                    raise ValueError('Invalid compute constant-buffer indices')
                yield vi, ki, layout, index, kv


def info(tree):
    native = list(descriptors(tree, C.METAL_RENDERER))
    source = list(descriptors(tree))
    if any(v.get('targetRenderer') == C.METAL_RENDERER for v in tree.get('variants', [])) and not native:
        raise ValueError('Metal compute renderer has no kernel variants')
    for vi, ki, layout, index, kv in native:
        code = bytes(kv['code'])
        if len(code) <= 20 or struct.unpack_from('<3I', code) != (0xDEADCAFE, 1, 20) or b'computeMain' not in code[20:]:
            raise ValueError('Unsupported or incomplete Metal compute payload')
        if list(struct.unpack_from('<3H', code, 12)) != list(kv['threadGroupSize']):
            raise ValueError('Metal compute thread group metadata mismatch')
    if native and source:
        names = lambda rows: {tree['variants'][vi]['kernels'][ki]['name'] for vi, ki, _, _, _ in rows}
        if not names(source).issubset(names(native)):
            raise ValueError('Metal compute renderer is missing required kernels')
        def keyword_coverage(renderer):
            coverage = set()
            for variant in tree['variants']:
                if variant['targetRenderer'] != renderer: continue
                for kernel in variant['kernels']:
                    pairs = kernel.get('variantMap', kernel.get('variantIndices', []))
                    coverage.update((variant.get('targetLevel'), kernel['name'], json.dumps(pair[0], sort_keys=True)) for pair in pairs)
            return coverage
        if not keyword_coverage(C.D3D11_RENDERER).issubset(keyword_coverage(C.METAL_RENDERER)):
            raise ValueError('Metal compute renderer is missing required keyword variants')
    if not native and not source:
        raise ValueError('No supported D3D11 or Metal compute variants')
    return {'metal': bool(native), 'kernels': len(native or source),
            'layouts': sorted({row[2] for row in native or source})}


def backend_key():
    digest = hashlib.sha256((COMMIT + platform.platform()).encode())
    for path in (HERE/'build_compute.sh', HERE/'compute_shader/dxbc2msl.cpp', HERE/'compute_shader/hlslcc-unity-player.patch', HERE/'hlslcc-structured-stride.patch'):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def backend():
    directory = CACHE / 'backend' / backend_key()
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / 'dxbc2msl'
    with (directory/'build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not binary.is_file():
            with (directory/'build.log').open('wb') as log:
                try:
                    result = subprocess.run(['sh', str(HERE/'build_compute.sh'), str(directory)], stdout=log, stderr=subprocess.STDOUT, timeout=300)
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise ComputeToolUnavailable(f'Cannot build compute translator; see {directory}/build.log: {error}') from error
            if result.returncode:
                raise ComputeToolUnavailable(f'Compute translator build failed; see {directory}/build.log')
    return binary


def translate(dxbc):
    binary = backend()
    key = hashlib.sha256(binary.read_bytes() + dxbc).hexdigest()
    folder = CACHE / 'programs' / key
    msl_path, reflection_path = folder/'source.metal', folder/'reflection.json'
    if not (msl_path.is_file() and reflection_path.is_file()):
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            prefix = Path(temporary)
            source, msl, reflection = prefix/'source.dxbc', prefix/'source.metal', prefix/'reflection.json'
            source.write_bytes(dxbc)
            try:
                result = subprocess.run([str(binary), str(source), str(msl), str(reflection)], capture_output=True, timeout=60)
            except OSError as error:
                raise ComputeToolUnavailable(f'Cannot execute compute translator: {error}') from error
            except subprocess.TimeoutExpired as error:
                raise ValueError('Compute translator timed out') from error
            if result.returncode or not msl.is_file() or not reflection.is_file():
                raise ValueError(f'Compute translation failed (exit {result.returncode}): ' + result.stderr.decode(errors='replace')[-1500:])
            parsed = json.loads(reflection.read_text())
            if not isinstance(parsed, list):
                raise ValueError('Invalid translator reflection')
            atomic_write(msl_path, msl.read_bytes())
            atomic_write(reflection_path, reflection.read_bytes())
    return msl_path.read_text(), json.loads(reflection_path.read_text())


def convert(tree):
    """Append Metal renderer variants only after every kernel has valid code and bindings."""
    if info(tree)['metal']:
        return None
    replacements = {}
    sources = []
    cb_tables = collections.defaultdict(list)
    cb_indices = collections.defaultdict(dict)
    for vi, ki, layout, index, kv in descriptors(tree):
        variant = tree['variants'][vi]
        dxbc = bytes(kv['code'])
        if len(dxbc) < 32 or dxbc[:4] != b'DXBC' or struct.unpack_from('<I', dxbc, 24)[0] != len(dxbc):
            raise ValueError('Invalid compute DXBC payload')
        msl, reflection = translate(C.fixed_dxbc(variant, kv))
        result = C.metal_kernel(kv, msl, reflection)
        # Validate exactly the MSL embedded into Unity's compute payload, after minification.
        sources.append(result['code'][20:])
        replacements[vi, ki, layout, index] = result
        for position, original_index in enumerate(kv['cbVariantIndices']):
            name = result['cbs'][position]['name']
            size, params = metal.struct_layout(msl, name+'_Type')
            descriptor = {'name': name, 'byteSize': size, 'params': [
                {'name': p['name'], 'type': p['type'], 'offset': p['index'], 'arraySize': p['arraySize'],
                 'rowCount': p['rows'] if p['isMatrix'] else 1, 'colCount': p['cols']} for p in params]}
            key = (original_index, json.dumps(descriptor, sort_keys=True))
            if key not in cb_indices[vi]:
                cb_indices[vi][key] = len(cb_tables[vi])
                cb_tables[vi].append(descriptor)
            result['cbVariantIndices'][position] = cb_indices[vi][key]
    require_valid(sources)
    output = copy.deepcopy(tree)
    for vi, variant in enumerate(tree['variants']):
        if variant['targetRenderer'] != C.D3D11_RENDERER:
            continue
        new = copy.deepcopy(variant)
        for ki, kernel in enumerate(new['kernels']):
            for layout, index, _ in kernel_variants(kernel):
                replacement = replacements[vi, ki, layout, index]
                if layout == 'variantMap':
                    kernel[layout][index] = [kernel[layout][index][0], replacement]
                else:
                    kernel[layout][index] = replacement
        new['constantBuffers'] = cb_tables[vi]
        new['targetRenderer'] = C.METAL_RENDERER
        output['variants'].append(new)
    return output


def patch_compute(tree, stats):
    if tree.get('m_Name') in set(filter(None, os.environ.get('SKIP_SHADER', '').split(','))):
        stats['compute_excluded'] += 1
        return False
    try:
        output = convert(tree)
        count = info(output)['kernels'] if output is not None else 0
    except (ValueError, KeyError, TypeError, IndexError, struct.error) as error:
        stats['compute_failed'] += 1
        print('Compute skipped:', tree.get('m_Name', '?'), error, flush=True)
        return False
    if output is None:
        stats['compute_has_metal'] += 1
        return False
    tree.clear()
    tree.update(output)
    stats['compute_patched'] += 1
    stats['compute_kernel_variants'] += count
    return True


def preflight(report):
    """Compile compute objects found by the shared inventory, without editing assets."""
    import UnityPy
    summary = {'objects': 0, 'kernel_variants': 0}
    for item in report['files']:
        rows = [row for row in item['shaders'] if row['kind'] == 'ComputeShader']
        if not any(not row['issues'] and not row.get('compute', {}).get('metal') for row in rows):
            continue
        objects = [obj for obj in UnityPy.load(item['path']).objects if obj.type.name == 'ComputeShader']
        if len(rows) != len(objects):
            raise ComputeToolUnavailable('Compute object inventory changed during preflight')
        for obj, row in zip(objects, rows):
            if obj.path_id != row['path_id']:
                raise ComputeToolUnavailable('Compute object inventory changed during preflight')
            if row['issues'] or row.get('compute', {}).get('metal'):
                continue
            try:
                output = convert(obj.read_typetree())
                if output is not None:
                    count = info(output)['kernels']
                    row['compute']['validated_kernel_variants'] = count
                    summary['objects'] += 1
                    summary['kernel_variants'] += count
            except (ValueError, KeyError, TypeError, IndexError, struct.error) as error:
                issue = {'code': 'compute_conversion_failed', 'file': item['path'], 'path_id': obj.path_id,
                         'name': row['name'], 'detail': f'{type(error).__name__}: {error}'}
                row['issues'].append(issue)
                report['issues'].append(issue)
    report['compute_translation'] = summary
