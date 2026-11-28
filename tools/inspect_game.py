#!/usr/bin/env python3
"""Go/no-go report for porting a Windows Unity game.  usage: inspect_game.py <game folder or Game_Data folder>
Prints: Unity version, scripting backend, render pipeline hints, shader graphics APIs, native plugins, Addressables."""
import sys, os, re, glob, collections
root = sys.argv[1]; data = root if root.endswith('_Data') else (glob.glob(f'{root}/*_Data') or [None])[0]
if not data: sys.exit('no *_Data folder found')
game = os.path.dirname(data)
if os.path.exists(f'{game}/GameAssembly.dll') or os.path.isdir(f'{data}/il2cpp_data'):
    print('Scripting backend : IL2CPP -> NOT supported by this toolkit')
    sys.exit(0)

try:
    with open(f'{data}/globalgamemanagers', 'rb') as managers:
        head = managers.read(512)
except FileNotFoundError:
    sys.exit(f'No loose globalgamemanagers in {data}. Use a Windows build with unpacked Unity data.')

ver = re.search(rb'\d{4}\.\d+\.\d+[fpab]\d+|\d{1}\.\d+\.\d+[fpab]\d+', head)
print('Unity version     :', ver.group().decode() if ver else '?  (strings <Data>/globalgamemanagers | head)')
print('Scripting backend :', 'Mono' if os.path.exists(f'{data}/Managed/Assembly-CSharp.dll') else '?')
print('Native plugins    :', ', '.join(sorted(os.path.basename(p) for p in glob.glob(f'{data}/Plugins/**/*.dll', recursive=True))) or 'none')
print('Addressables      :', 'yes (StreamingAssets/aa) - needs the path fix + possible bundle patching' if os.path.isdir(f'{data}/StreamingAssets/aa') else 'no')
from shader_coverage import scan

report, _ = scan(data)
names, plats, n = [], collections.Counter(), 0
for item in report['files']:
    for shader in item['shaders']:
        if shader['kind'] != 'Shader': continue
        n += 1; names.append(shader['name'])
        for p in set(shader.get('platforms', [])): plats[p] += 1
print('Compute shaders   :', report['counts'].get('ComputeShader', 0), f"(Metal present: {report['counts'].get('ComputeWithMetal', 0)}; preflight required)")
print('Coverage issues   :', len(report['issues']))
PLAT = {4: 'D3D11', 9: 'GLES3+', 14: 'Metal', 15: 'OpenGLCore', 18: 'Vulkan', 26: 'D3D12/other'}
print(f'Shaders           : {n};', ', '.join(f'{PLAT.get(p, p)}:{c}' for p, c in sorted(plats.items())))
hd = sum('HDRP' in x for x in names); ur = sum(x.startswith(('Universal Render Pipeline', 'Shader Graphs')) for x in names)
print('Render pipeline   :', 'HDRP shader names found -> full pipeline compatibility is unverified' if hd else ('URP/ShaderGraph shaders present' if ur else 'built-in (best case)'))
print('Metal already in  :', 'yes (a native build may exist)' if plats.get(14, 0) > 6 else 'no (only Unity internal shaders have it)')
print('Verdict hint      :', 'candidate for translation checks (not a playability guarantee)' if (not hd and plats.get(4) and not report['issues']) else 'blocked - see docs/PORTING-A-NEW-GAME.md')
