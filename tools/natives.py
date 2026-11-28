#!/usr/bin/env python3
"""Install macOS stand-ins for the Windows-only native plugins a Unity game ships (the game's x86_64 .dll files cannot load).
usage: natives.py --app <App>.app [--tweaks] [--steam] [--discord] [--voice] [--dissonance]      (then re-sign the app)
  --tweaks   metalport_tweaks.dylib: mouse scale, App Nap off, first-run shader warm-up (injected by launch.sh)
  --steam    arm64 libsteam_api (borrowed from any installed Steam game) + a shim adding newer flat-API calls; maps steam_api64
  --discord  no-op libdiscord_partner_sdk stand-in (the game stops throwing DllNotFound every frame)
  --voice    Photon Voice: stock libopus as opus_egpv + pass-through WebRTC/AudioIn stubs (needs `brew install opus`)
  --dissonance  Dissonance Voice Chat (Lethal Company): pass-through AudioPluginDissonance stand-in with a loudness-gate speech detector (MP_VAD_DB)"""
import argparse, glob, os, re, shutil, subprocess, sys
ap = argparse.ArgumentParser(); ap.add_argument('--app', required=True)
for f in ('tweaks', 'steam', 'discord', 'voice', 'dissonance'): ap.add_argument(f'--{f}', action='store_true')
a = ap.parse_args(); here = os.path.dirname(os.path.abspath(__file__)); C = f'{a.app}/Contents'; P = f'{C}/Plugins'; M = f'{C}/Resources/Data/Managed'
os.makedirs(P, exist_ok=True); run = lambda *c: subprocess.run(c, check=True)
cc = lambda src, out, *extra: run('clang', '-dynamiclib', '-arch', 'arm64', '-Wno-everything', src, '-o', out, '-install_name', f'@loader_path/{os.path.basename(out)}', *extra)
sign = lambda p: subprocess.run(['codesign', '--force', '-s', '-', p], check=True, capture_output=True)
def dllmap(dll, lib):
    p = f'{C}/MonoBleedingEdge/etc/mono/config'; t = open(p).read()
    if f'dll="{dll}"' not in t: open(p, 'w').write(t.replace('</configuration>', f'\t<dllmap dll="{dll}" target="@executable_path/../Plugins/{lib}"/>\n</configuration>'))
def strings(path): return set(re.findall(rb'[A-Za-z0-9_\-]{5,}', open(path, 'rb').read()))
def exports(lib): return set(subprocess.run(['nm', '-gU', lib], capture_output=True, text=True).stdout.split()[2::3])

if a.tweaks:
    out = f'{P}/metalport_tweaks.dylib'; run('clang', '-dynamiclib', '-arch', 'arm64', '-fobjc-arc', '-framework', 'Cocoa', '-framework', 'ApplicationServices', f'{here}/tweaks.m', '-o', out); sign(out); print('tweaks ok')
if a.discord:
    syms = sorted({s.decode() for s in strings(f'{M}/Discord.Sdk.dll') if s.startswith(b'Discord_')})
    open('/tmp/discord_stub.c', 'w').write(''.join(f'long {s}(void) {{ return 0; }}\n' for s in syms)); out = f'{P}/libdiscord_stub.dylib'
    cc('/tmp/discord_stub.c', out); sign(out); dllmap('discord_partner_sdk', 'libdiscord_stub.dylib'); print(f'discord stub ok ({len(syms)} functions)')
if a.voice:
    opus = '/opt/homebrew/lib/libopus.0.dylib'; assert os.path.exists(opus), 'brew install opus'
    shutil.copyfile(opus, f'{P}/libopus.0.dylib'); run('install_name_tool', '-id', '@loader_path/libopus.0.dylib', f'{P}/libopus.0.dylib'); sign(f'{P}/libopus.0.dylib')
    cc(f'{here}/voice_shim.c', f'{P}/libopus_egpv.dylib', '-I/opt/homebrew/include/opus', f'{P}/libopus.0.dylib', f'-Wl,-reexport_library,{P}/libopus.0.dylib')
    cc(f'{here}/photon_stub.c', f'{P}/libphoton_stub.dylib')
    for l in ('libopus_egpv', 'libphoton_stub'): sign(f'{P}/{l}.dylib')
    for dll, lib in (('opus_egpv', 'libopus_egpv.dylib'), ('webrtc-audio', 'libphoton_stub.dylib'), ('AudioIn', 'libphoton_stub.dylib')): dllmap(dll, lib)
    print('voice ok')
if a.dissonance:
    cc(f'{here}/dissonance_stub.c', f'{P}/libdissonance_stub.dylib'); sign(f'{P}/libdissonance_stub.dylib')
    dllmap('AudioPluginDissonance', 'libdissonance_stub.dylib'); print('dissonance ok')
if a.steam:
    need = set()
    for f in glob.glob(f'{M}/*.dll'): need |= {s.decode() for s in strings(f) if re.fullmatch(rb'SteamAPI_Steam\w+_v\d+', s)}
    root = os.path.expanduser('~/Library/Application Support/Steam/steamapps/common')
    cands = subprocess.run(['find', root, '-maxdepth', '9', '-name', 'libsteam_api.dylib'], capture_output=True, text=True).stdout.splitlines()   # bounded search
    best = None
    for c in cands:
        if 'arm64' not in subprocess.run(['lipo', '-archs', c], capture_output=True, text=True).stdout: continue
        e = {s.lstrip('_') for s in exports(c)}
        if 'SteamInternal_SteamAPI_Init' in e: best = max(best or (-1, c), (len(need & e), c))
    assert best, 'no arm64 libsteam_api.dylib with SteamInternal_SteamAPI_Init found among installed Steam games'
    lib = best[1]; e = {s.lstrip('_') for s in exports(lib)}; missing = sorted(need - e)
    names = {'UGC': 'STEAMUGC_INTERFACE_VERSION', 'UserStats': 'STEAMUSERSTATS_INTERFACE_VERSION', 'Video': 'STEAMVIDEO_INTERFACE_V', 'Timeline': 'STEAMTIMELINE_INTERFACE_V', 'Apps': 'STEAMAPPS_INTERFACE_VERSION'}
    code = 'extern void* SteamInternal_FindOrCreateUserInterface(int, const char*);\nextern int SteamAPI_GetHSteamUser(void);\nextern int SteamGameServer_GetHSteamUser(void);\n'
    for s in missing:
        m = re.fullmatch(r'SteamAPI_Steam(GameServer)?(\w+?)_v(\d+)', s)
        if not m or m.group(2) not in names: print('WARNING cannot shim', s); continue
        user = 'SteamGameServer_GetHSteamUser' if m.group(1) else 'SteamAPI_GetHSteamUser'
        code += f'void* {s}(void) {{ return SteamInternal_FindOrCreateUserInterface({user}(), "{names[m.group(2)]}{m.group(3)}"); }}\n'
    LEGACY = {      # entry points older Steamworks.NET builds call that newer SDKs dropped
        'SteamAPI_Init': 'extern _Bool SteamAPI_InitSafe(void);\n_Bool SteamAPI_Init(void) { return SteamAPI_InitSafe(); }\n',
        'SteamAPI_ISteamUserStats_RequestCurrentStats': '_Bool SteamAPI_ISteamUserStats_RequestCurrentStats(void* self) { return 1; }\n',   # SDK 1.61+: stats load automatically
    }
    for i in ('GameSearch', 'MusicRemote', 'AppList'):     # interfaces later SDKs dropped from the flat API; Steamworks.NET's context init fails on a null one
        LEGACY[f'SteamAPI_ISteamClient_GetISteam{i}'] = f'void* SteamAPI_ISteamClient_GetISteam{i}(void* self, int user, int pipe, const char* ver) {{ return SteamInternal_FindOrCreateUserInterface(user, ver); }}\n'
    used = set().union(*(strings(f) for f in glob.glob(f'{M}/*.dll')))
    if b'SteamAPI_ISteamClient_GetISteamUser' in used and not any(re.fullmatch(rb'SteamAPI_SteamUser_v\d+', s) for s in used):
        # old Steamworks.NET: SteamClient()->GetISteamX(ver) with its own (older) versions.  The borrowed lib's flat functions assume ITS
        # vtable layouts, so hand out its client and its interface versions (matched by name prefix) instead of the requested ones.
        vers = sorted({s.decode() for s in strings(lib) if re.fullmatch(rb'(STEAM\w+?_(INTERFACE_)?V(ERSION)?_?|Steam[A-Za-z]+)\d{3}', s)})
        client = max(v for v in vers if v.startswith('SteamClient'))
        code += 'extern void* SteamInternal_CreateInterface(const char*);\n#include <string.h>\n#include <ctype.h>\n'
        code += 'static const char* V[] = {' + ','.join(f'"{v}"' for v in vers) + '};\n'
        code += ('static const char* pick(const char* want) { size_t n = strlen(want); while (n && isdigit((unsigned char)want[n-1])) n--;\n'
                 '  for (unsigned i = 0; i < sizeof V / sizeof *V; i++) if (strlen(V[i]) == n + 3 && !strncmp(V[i], want, n)) return V[i]; return want; }\n'
                 f'void* SteamClient(void) {{ return SteamInternal_CreateInterface("{client}"); }}\n')
        for x in ('User', 'Friends', 'Apps', 'UGC', 'UserStats', 'Video', 'RemotePlay', 'Matchmaking', 'MatchmakingServers', 'Networking', 'RemoteStorage',
                  'Screenshots', 'HTTP', 'Music', 'HTMLSurface', 'Inventory', 'ParentalSettings', 'Input', 'Parties', 'Controller'):
            LEGACY[f'SteamAPI_ISteamClient_GetISteam{x}'] = f'void* SteamAPI_ISteamClient_GetISteam{x}(void* self, int user, int pipe, const char* ver) {{ return SteamInternal_FindOrCreateUserInterface(user, pick(ver)); }}\n'
        e = e - set(LEGACY)                                  # override the lib's own versions of these getters
        LEGACY['SteamClient'] = ''; e.discard('SteamClient')
    for s, c in LEGACY.items():
        if s.encode() in used and s not in e: code += c; missing.append(s)
    base = f'{P}/libsteam_api_base.dylib'; run('lipo', lib, '-thin', 'arm64', '-output', base); subprocess.run(['install_name_tool', '-id', '@loader_path/libsteam_api_base.dylib', base], capture_output=True); sign(base)
    open('/tmp/steamshim.c', 'w').write(code); cc('/tmp/steamshim.c', f'{P}/libsteam_api.dylib', base, f'-Wl,-reexport_library,{base}'); sign(f'{P}/libsteam_api.dylib')
    dllmap('steam_api64', 'libsteam_api.dylib'); print(f'steam ok (base lib: {os.path.basename(os.path.dirname(lib))}, shimmed {len(missing)} symbols)')
