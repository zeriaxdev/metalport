#!/usr/bin/env python3
"""Assemble a Mac Unity app only after shader translation and Metal compilation checks.
Native plugins, signing and gameplay verification remain separate steps; see docs/.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from shader_coverage import scan, finish
from patch_bundles import patch_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'unity', 'out', 'name'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--skip-shader', default='')
    parser.add_argument('--allow-incomplete', action='store_true', help='Keep shader gaps visible and produce an explicitly incomplete app')
    parser.add_argument('--dev', action='store_true')
    args = parser.parse_args(argv)
    here = Path(__file__).resolve().parent
    output = Path(args.out).resolve()
    app = output / (args.name + '.app')
    if app.exists():
        parser.error(f'{app} exists; use a new output directory')
    if Path(args.data).resolve() in app.parents:
        parser.error('The output app must be outside the source Data directory')
    run = lambda *command: subprocess.run(command, check=True)
    translator = here / 'h2m'
    build_inputs = [here / 'build_hlslcc.sh', here / 'h2m.cpp', *here.glob('hlslcc-*.patch')]
    if not translator.is_file() or any(path.stat().st_mtime_ns > translator.stat().st_mtime_ns for path in build_inputs):
        run('sh', str(here / 'build_hlslcc.sh'))
    output.mkdir(parents=True, exist_ok=True)
    run(sys.executable, str(here / 'xlate_all.py'), args.data,
        '--report', str(output / 'shader-source-coverage.json'), '--skip-shader', args.skip_shader,
        *(['--allow-incomplete'] if args.allow_incomplete else []))
    run(sys.executable, str(here / 'assemble_app.py'), '--data', args.data, '--unity', args.unity,
        '--out', str(output), '--name', args.name, *(['--dev'] if args.dev else []))
    target = app / 'Contents/Resources/Data'
    inventory, _ = scan(target, set(filter(None, args.skip_shader.split(','))))
    if any(issue['code'] == 'read_error' for issue in inventory['issues']):
        finish(inventory, output / 'shader-output-coverage.json')
        return 2
    os.environ['SKIP_SHADER'] = args.skip_shader
    os.environ['ALLOW_PARTIAL_SHADER'] = '1' if args.allow_incomplete else '0'
    for item in inventory['files']:
        if any(shader['kind'] in ('Shader', 'ComputeShader') for shader in item['shaders']):
            try:
                patch_file(Path(item['path']))
            except Exception as error:
                inventory['phase'] = 'output'
                inventory['issues'].append({'code': 'injection_failed', 'file': item['path'], 'detail': f'{type(error).__name__}: {error}'})
                finish(inventory, output / 'shader-output-coverage.json')
                return 2
    report, _ = scan(target, set(filter(None, args.skip_shader.split(','))), audit=True)
    complete = finish(report, output / 'shader-output-coverage.json')
    fatal = any(issue['code'] in ('read_error', 'no_shaders') for issue in report['issues'])
    if fatal or (not complete and not args.allow_incomplete):
        return 2
    print(('Shader coverage complete.' if complete else 'INCOMPLETE shader coverage (--allow-incomplete).') +
          ' Next: add native plugins, sign, and verify rendering/audio/networking; see docs/.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
