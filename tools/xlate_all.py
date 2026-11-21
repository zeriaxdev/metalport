"""Translate loose and bundled D3D11 programs, validate MSL, and write coverage JSON."""
import argparse
import hashlib
import json
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

from dxbc_rdef import add_rdef
from metal_check import MetalCheckUnavailable, atomic_write, validate_sources
from shader_coverage import scan, finish
from compute_support import preflight as compute_preflight, ComputeToolUnavailable

S = Path(__file__).resolve().parent
FLAGS = '0x1020081'


def converter_identity():
    digest = hashlib.sha256(FLAGS.encode())
    for name in ('h2m', 'dxbc_rdef.py', 'xlate_all.py'):
        digest.update((S / name).read_bytes())
    return digest.hexdigest()


def work(job):
    h, identity = job
    path = S / 'cache' / h
    metal = path.with_suffix('.metal')
    metadata = path.with_suffix('.translation.json')
    try:
        if metal.is_file() and metadata.is_file():
            recorded = json.loads(metadata.read_text())
            if recorded == {'converter': identity, 'msl': hashlib.sha256(metal.read_bytes()).hexdigest()}:
                return h, ''
        dx = path.with_suffix('.dxbc').read_bytes()
        atomic_write(metadata, json.dumps({'converter': identity, 'failed': True}).encode())
        rdef = path.with_suffix('.rdef.dxbc')
        atomic_write(rdef, add_rdef(dx))
        result = subprocess.run([str(S / 'h2m'), str(rdef), FLAGS], capture_output=True, timeout=60)
        if result.returncode or not result.stdout.strip():
            return h, f'rc={result.returncode}: ' + result.stderr.decode(errors='replace')[:1000]
        atomic_write(metal, result.stdout)
        atomic_write(metadata, json.dumps({'converter': identity, 'msl': hashlib.sha256(result.stdout).hexdigest()}).encode())
        return h, ''
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return h, f'{type(error).__name__}: {error}'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data')
    parser.add_argument('--report', default='shader-coverage.json')
    parser.add_argument('--skip-shader', default='')
    parser.add_argument('--allow-incomplete', action='store_true', help='Continue with reported shader gaps; does not mark the report complete')
    parser.add_argument('--audit-only', action='store_true', help='Check output coverage without translating or writing game assets')
    args = parser.parse_args(argv)
    try:
        report, jobs = scan(args.data, set(filter(None, args.skip_shader.split(','))), args.audit_only)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    fatal = any(issue['code'] in ('read_error', 'no_shaders') for issue in report['issues'])
    if jobs and not args.audit_only:
        try:
            identity = converter_identity()
        except OSError as error:
            report['issues'].append({'code': 'translator_unavailable', 'detail': str(error)})
            finish(report, args.report)
            return 2
        for h, dxbc in jobs.items():
            atomic_write(S / 'cache' / (h + '.dxbc'), dxbc)
        errors = {}
        with Pool(min(10, len(jobs))) as pool:
            for h, error in pool.imap_unordered(work, [(h, identity) for h in jobs], chunksize=8):
                if error:
                    errors[h] = error
        translated = {h: (S / 'cache' / (h + '.metal')).read_bytes() for h in jobs if h not in errors}
        try:
            invalid = validate_sources(translated.values())
        except MetalCheckUnavailable as error:
            report['issues'].append({'code': 'validator_unavailable', 'detail': str(error)})
            finish(report, args.report)
            return 2
        for item in report['files']:
            for shader in item['shaders']:
                for h in sorted({p['hash'] for p in shader['programs']}):
                    digest = hashlib.sha256(translated[h]).hexdigest() if h in translated else None
                    code = 'translation_failed' if h in errors else 'metal_compile_failed' if digest in invalid else None
                    if code:
                        issue = {'code': code, 'file': item['path'], 'path_id': shader['path_id'], 'name': shader['name'],
                                 'hash': h, 'detail': errors[h] if h in errors else invalid[digest]}
                        shader['issues'].append(issue)
                        report['issues'].append(issue)
        report['translation'] = {'unique': len(jobs), 'translated': len(translated), 'metal_validated': sum(hashlib.sha256(s).hexdigest() not in invalid for s in translated.values()), 'converter': identity}
    if not args.audit_only and not fatal:
        try:
            compute_preflight(report)
        except (MetalCheckUnavailable, ComputeToolUnavailable) as error:
            report['issues'].append({'code': 'compute_tool_unavailable', 'detail': str(error)})
            finish(report, args.report)
            return 2
    complete = finish(report, args.report)
    return 0 if complete or (args.allow_incomplete and not fatal) else 2


if __name__ == '__main__':
    sys.exit(main())
