#!/usr/bin/env python3
"""One command for the whole shader-and-app pipeline on a Windows Unity (Mono, D3D11) game.
usage: port.py --data <Game>_Data --unity <fetch_unity out> --out <dir> --name <App> [--skip-shader NAME,...]
Afterwards: natives (tools/natives.py), then `codesign --force --deep -s - <App>.app`.  See docs/."""
import argparse, os, subprocess, sys
ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--unity', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--name', required=True); ap.add_argument('--skip-shader', default=''); ap.add_argument('--dev', action='store_true'); a = ap.parse_args()
here = os.path.dirname(os.path.abspath(__file__)); py = sys.executable; run = lambda *c, **k: subprocess.run(c, check=True, **k)
if not os.path.exists(f'{here}/h2m'): run('sh', f'{here}/build_hlslcc.sh')
os.makedirs(a.out, exist_ok=True)
run(py, f'{here}/assemble_app.py', '--data', a.data, '--unity', a.unity, '--out', a.out, '--name', a.name, *(['--dev'] if a.dev else []))
os.makedirs(f'{here}/cache', exist_ok=True)
run(py, f'{here}/xlate_all.py', a.data)                                                       # D3D11 bytecode -> Metal source (cache/)
env = dict(os.environ, SKIP_SHADER=a.skip_shader)
run(py, f'{here}/inject_inplace.py', f'{a.out}/{a.name}.app/Contents/Resources/Data', env=env) # append Metal variants to the Shader objects
print('done: now add natives (tools/natives.py), sign, launch with tools/launch.sh')
